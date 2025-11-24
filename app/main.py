from fastapi import Request, Response
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
import os
import hashlib
import json as jsonlib
import json as _json
from fastapi import HTTPException, Header, Body
import psycopg
import datetime as dt



# --- CORS (frontend local sur 3000) ---
app = FastAPI()


# --- Cache-Control pour /api/signals (GET/HEAD) ---
def _signals_cache_mw():
    @app.middleware("http")
    async def _cache_signals(request: Request, call_next):
        resp = await call_next(request)
        if request.url.path.startswith("/api/signals") and request.method in ("GET","HEAD"):
            resp.headers["Cache-Control"] = "public, max-age=10"
        return resp
_signals_cache_mw()

# --- CORS (frontend local sur 3000) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET","POST","OPTIONS"],
    allow_headers=["*"],
)

rows = []  # safe default to avoid import crash at module load
first = None
last = None

# --- ETag helper (local, sans middleware) ---
def json_with_etag(payload, request: Request, max_age: int = 15) -> Response:
    body = _json.dumps(jsonable_encoder(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    etag = hashlib.sha1(body).hexdigest()
    inm = request.headers.get("if-none-match")
    headers = {"ETag": etag, "Cache-Control": f"public, max-age={max_age}"}
    if inm == etag:
        return Response(status_code=304, headers=headers, media_type="application/json")
    return Response(content=body, headers=headers, media_type="application/json")
def _json_with_etag(payload, request: Request) -> Response:
    # Sérialisation stable (dates -> iso via jsonable_encoder, clés triées pour hash stable)
    body = jsonlib.dumps(
        jsonable_encoder(payload),
        separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    etag = hashlib.sha1(body).hexdigest()
    inm = request.headers.get("if-none-match")
    headers = {"ETag": etag, "Cache-Control": "public, max-age=15"}
    if inm == etag:
        return Response(status_code=304, headers=headers, media_type="application/json")
    return Response(content=body, headers=headers, media_type="application/json")
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import re

from app.db import init_db
from app.auth import (
    get_user_by_email, verify_password, create_access_token, decode_token, get_user_by_id
)
from app.settings import INTERNAL_TOKEN
from app.scoring import recompute_daily
from app.sources.bodacc import collect as bodacc_collect

# app.add_middleware(ETagSignalsMiddleware)  # disabled: called before app init

# Static & templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "app_name": "Radar FR"})

@app.get("/documents", response_class=HTMLResponse)
def documents_page(request: Request):
    return templates.TemplateResponse("documents.html", {"request": request, "app_name": "Radar FR"})

@app.get("/healthz")
def healthz():
    return {"ok": True, "env": {"DB_URL_set": bool(os.getenv("DB_URL")), "port": os.getenv("PORT", "8080")}}

@app.post("/admin/init-db")
def admin_init_db():
    init_db()
    return {"ok": True, "message": "DB initialized"}

class LoginBody(BaseModel):
    email: str
    password: str

@app.post("/auth/login")
def login(body: LoginBody):
    user = get_user_by_email(body.email.lower())
    if not user or (not verify_password(body.password, user["password_hash"])):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user["id"]), "client_id": user["client_id"]})
    return {"access_token": token, "token_type": "bearer", "user": {
        "id": user["id"], "client_id": user["client_id"], "full_name": user["full_name"],
        "email": user["email"], "role": user["role"]
    }}

@app.get("/me")
def me(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        data = decode_token(token)
        user_id = int(data["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user": user}

# ----------- ROUTES INTERNES (collector) -----------
@app.get("/collector/bodacc")
def collector_bodacc(token: str = Query(default=""), limit: int = Query(default=8, ge=1, le=50)):
    if token != INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid internal token")
    data = bodacc_collect(limit=limit)
    return {"ok": True, "source": "BODACC", "count": len(data), "items": data}
DB_URL = os.getenv("DB_URL", "postgresql://radar:radarpass@db:5432/radar")

@app.post("/collector/bodacc/ingest")
def collector_bodacc_ingest(token: str = Query(default=""), limit: int = Query(default=8, ge=1, le=50)):
    if token != INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid internal token")

    items = bodacc_collect(limit=limit)
    inserted = 0
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            for it in items:
                # 1) Extraire SIREN s'il est présent
                m = re.search(r"(SIREN\s+)?(\d{9})", it["text"])
                siren = m.group(2) if m else None

                # 2) Upsert company (si SIREN détecté)
                company_id = None
                if siren:
                    cur.execute("""
                        insert into company (country, siren, name)
                        values ('FR', %s, coalesce(%s,'Inconnue'))
                        on conflict (siren) do update set updated_at=now()
                        returning id;
                    """, (siren, None))
                    row = cur.fetchone()
                    company_id = row[0] if row else None

                # 3) Classifier le type de signal (MVP)
                txt = it["text"].lower()
                if "redressement judiciaire" in txt or "liquidation judiciaire" in txt:
                    sig_type = "PROC_COLLECTIVE"; weight = 100; conf = 0.95
                elif "cession de fonds" in txt:
                    sig_type = "SALE_OF_BUSINESS"; weight = 70; conf = 0.80
                elif "fusion" in txt:
                    sig_type = "M&A_PROJECT"; weight = 60; conf = 0.70
                else:
                    sig_type = "OTHER"; weight = 30; conf = 0.50

                # 4) Insérer le signal (éviter doublons par URL)
                cur.execute("""
   	 		insert into signal (company_id, source, type, event_date, url, excerpt, weight, confidence)
    			values (%s, 'BODACC', %s, %s, %s, %s, %s, %s)
    			on conflict (url) do update
      				set event_date = excluded.event_date,
          				excerpt    = excluded.excerpt,
          				weight     = excluded.weight,
          				confidence = excluded.confidence,
          				company_id = coalesce(signal.company_id, excluded.company_id),
          				type       = excluded.type;
		""", (
   	 		company_id, sig_type, it["event_date"],
    			it["url"], it["text"], weight, conf
		))

    return {"ok": True, "inserted": inserted, "count_source": len(items)}
from typing import Optional, List, Dict

@app.post("/admin/score-daily")
def admin_score_daily(token: str = Query(default=""), date: str | None = Query(default=None)):
    from app.settings import INTERNAL_TOKEN  # sécurité: lit depuis l'env au runtime
    if token != INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid internal token")
    try:
        if date:
            dt.date.fromisoformat(date)  # YYYY-MM-DD
    except Exception:
        raise HTTPException(status_code=400, detail="Bad date format, expected YYYY-MM-DD")
    n = recompute_daily(date)
    return {"ok": True, "updated_rows": n, "date": date}

@app.get("/api/scores/daily")
def api_scores_daily(date: Optional[str] = None, limit: int = Query(default=50, ge=1, le=200)):
    """
    Retourne les sociétés scorées pour une date (YYYY-MM-DD).
    Par défaut: aujourd'hui.
    """
    # Normalisation défensive
    if not date:
        date_str = dt.date.today().isoformat()
    else:
        date_str = str(date).strip().strip('"').strip("'")
        if len(date_str) >= 10:
            date_str = date_str[:10]

    # Validation stricte
    try:
        dt.date.fromisoformat(date_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Bad date format, expected YYYY-MM-DD")

    rows: List[Dict] = []
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select
                  cs.company_id,
                  coalesce(c.name, 'Inconnue') as company_name,
                  c.siren,
                  cs.score_date,
                  cs.score_total,
                  cs.top_signal_type
                from company_score_daily cs
                left join company c on c.id = cs.company_id
                where cs.score_date = %s::date
                order by cs.score_total desc
                limit %s;
            """, (date_str, limit))
            for (company_id, company_name, siren, score_date, score_total, top_signal_type) in cur.fetchall():
                rows.append({
                    "company_id": company_id,
                    "company_name": company_name,
                    "siren": siren,
                    "score_date": score_date.isoformat(),
                    "score_total": int(score_total),
                    "top_signal_type": top_signal_type,
                })
    return {"ok": True, "date": date_str, "count": len(rows), "items": rows}
@app.get("/api/scores/latest")
def api_scores_latest(limit: int = Query(default=50, ge=1, le=200)):
    today = dt.date.today().isoformat()
    return api_scores_daily(date=today, limit=limit)
# --- FEEDBACK ANALYSTE SUR LES SIGNAUX ---
from typing import Literal


ALLOWED_LABELS = {"reliable", "unclear", "broken_link", "false_positive"}

class FeedbackBody(BaseModel):
    label: Literal["reliable", "unclear", "broken_link", "false_positive"]
    note: str | None = None

def _require_user_id(authorization: str | None) -> int:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        data = decode_token(token)
        return int(data["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/api/signals/{signal_id}/feedback")
def create_or_update_signal_feedback(
    signal_id: int,
    body: FeedbackBody = Body(...),
    authorization: str | None = Header(default=None),
):
    user_id = _require_user_id(authorization)
    label = body.label
    note = (body.note or "").strip()
    if label not in ALLOWED_LABELS:
        raise HTTPException(status_code=422, detail="Unknown label")

    if len(note) > 2000:
        note = note[:2000]

    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            # 404 si le signal n'existe pas
            cur.execute("select 1 from signal where id = %s;", (signal_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Signal not found")

            # UPSERT idempotent (signal_id, user_id)
            cur.execute("""
                insert into signal_feedback (signal_id, user_id, label, note)
                values (%s, %s, %s, nullif(%s, ''))
                on conflict (signal_id, user_id) do update
                    set label = excluded.label,
                        note  = excluded.note,
                        created_at = now()
                returning id, signal_id, user_id, label, note, created_at;
            """, (signal_id, user_id, label, note))
            row = cur.fetchone()

    return {"ok": True, "item": {
        "id": row[0], "signal_id": row[1], "user_id": row[2],
        "label": row[3], "note": row[4], "created_at": row[5].isoformat()
    }}

@app.get("/api/signals/{signal_id}/feedback")
def get_signal_feedback(signal_id: int, limit: int = Query(default=10, ge=1, le=50)):
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select label, count(*) as n
                from signal_feedback
                where signal_id = %s
                group by label
                order by label;
            """, (signal_id,))
            counts = [{"label": r[0], "count": int(r[1])} for r in cur.fetchall()]

            cur.execute("""
                select sf.label, sf.note, sf.user_id, sf.created_at
                from signal_feedback sf
                where sf.signal_id = %s
                order by sf.created_at desc
                limit %s;
            """, (signal_id, limit))
            latest = [{
                "label": r[0],
                "note": r[1],
                "user_id": r[2],
                "created_at": r[3].isoformat(),
            } for r in cur.fetchall()]

    return {"ok": True, "signal_id": signal_id, "counts": counts, "latest": latest}
@app.post("/auth/dev-login")
def dev_login(token: str = Query(default=""), user_id: int = Query(default=1)):
    # Protégé par l'INTERNAL_TOKEN, donc utilisable uniquement en interne/dev
    if token != INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid internal token")
    jwt = create_access_token({"sub": str(user_id), "client_id": 0})
    return {"access_token": jwt, "token_type": "bearer"}
	
# --- UI Signals (liste + feedback) ---
from fastapi.responses import HTMLResponse

@app.get("/signals", response_class=HTMLResponse)
def signals_page(
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    q: str | None = Query(default=None),
    sig_type: str | None = Query(default=None),
    label: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
):
    # Build filtres
    where = ["1=1"]
    params: list = []

    if q and q.strip():
        where.append("(s.excerpt ILIKE %s OR c.name ILIKE %s OR c.siren ILIKE %s)")
        v = f"%{q.strip()}%"
        params += [v, v, v]

    if sig_type and sig_type.strip():
        where.append("s.type = %s")
        params.append(sig_type.strip())

    if date_from:
        where.append("s.event_date >= %s::date")
        params.append(date_from)

    if date_to:
        where.append("s.event_date <= %s::date")
        params.append(date_to)

    if label and label.strip():
        where.append(
            "EXISTS (select 1 from signal_feedback sf "
            "where sf.signal_id = s.id and sf.label = %s)"
        )
        params.append(label.strip())

    where_sql = " AND ".join(where)

    # Derniers signaux
    rows: list[dict] = []
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select s.id,
                       coalesce(c.name,'Inconnue') as company_name,
                       c.siren,
                       s.type,
                       s.event_date,
                       s.url,
                       s.excerpt,
                       s.weight,
                       s.confidence
                  from signal s
             left join company c on c.id = s.company_id
                 where {where_sql}
              order by s.event_date desc, s.id desc
                 limit %s;
                """,
                (*params, limit),
            )
            cols = [d[0] for d in cur.description]
            for r in cur.fetchall():
                rows.append(dict(zip(cols, r)))

    # Feedback counts pour ces signaux
    counts: dict[int, dict[str, int]] = {}
    if rows:
        ids = [r["id"] for r in rows]
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select signal_id, label, count(*) as n
                      from signal_feedback
                     where signal_id = ANY(%s)
                     group by signal_id, label;
                    """,
                    (ids,),
                )
                for sid, lbl, n in cur.fetchall():
                    counts.setdefault(sid, {})[lbl] = int(n)

    return templates.TemplateResponse(
        "signals.html",
        {
            "request": request,
            "items": rows,
            "counts": counts,
            "allowed_labels": [
                "reliable",
                "unclear",
                "broken_link",
                "false_positive",
            ],
            "app_name": "Radar FR",
        },
    )



# --- INTERNAL: check source links and tag broken_link ---
import urllib.request
import urllib.error
import socket
from app.scheduler import start_jobs  # ensured by patch

@app.on_event("startup")
async def _start_jobs():
    start_jobs(app)

def internal_check_links(
    token: str = Query(default=""),
    lookback_days: int = Query(default=14, ge=1, le=90),
    limit: int = Query(default=200, ge=1, le=1000),
):
    if token != INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid internal token")

    # 1) Récupère des signaux récents
    items = []
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select id, url
                  from signal
                 where event_date >= (current_date - %s::int)
                 order by event_date desc, id desc
                 limit %s;
            """, (lookback_days, limit))
            items = cur.fetchall()
    def head_status(url: str, timeout: float = 5.0) -> int | None:
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return getattr(resp, "status", 200)
        except urllib.error.HTTPError as e:
            # si 403/405 sur HEAD, tente un GET léger
            if e.code in (403,405):
                try:
                    req = urllib.request.Request(url, method="GET")
                    # ne télécharge pas tout : on s'arrête dès l'entête
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        return getattr(resp, "status", 200)
                except Exception:
                    pass
            return e.code
        except (urllib.error.URLError, socket.timeout, ValueError):
            return None  # échec réseau/timeout/URL invalide

    broken, ok = 0, 0
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            for sid, url in items:
                st = head_status(url)
                is_broken = (st is None) or (st >= 400)
                if is_broken:
                    broken += 1
                    # upsert par (signal_id, user_id=0) — « système »
                    cur.execute("""
                        insert into signal_feedback (signal_id, user_id, label, note)
                        values (%s, 0, 'broken_link', %s)
                        on conflict (signal_id, user_id) do update
                          set label='broken_link',
                              note=excluded.note,
                              created_at=now();
                    """, (sid, f"auto(check-links): status={st}"))
                else:
                    ok += 1

    return {"ok": True, "scanned": len(items), "ok": ok, "broken_tagged": broken}

# --- pagination helpers ---
def _encode_cursor(d, i):  # d: date, i: id
    return f"{d}|{i}"

def _decode_cursor(c):
    try:
        d, i = c.split("|", 1)
        return d[:10], int(i)
    except Exception:
        raise HTTPException(status_code=400, detail="Bad cursor")

class ETagSignalsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        try:
            # Ne gère que GET /api/signals*
            if request.method != "GET":
                return response
            path = request.url.path
            if not path.startswith("/api/signals"):
                return response

            # Reconstitue le body (il faut le lire pour hasher)
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            etag = hashlib.sha1(body).hexdigest()
            inm = request.headers.get("if-none-match")

            from starlette.responses import Response as _StarResp

            # 304 si identique
            if inm == etag:
                r = _StarResp(status_code=304)
                r.headers["ETag"] = etag
                r.headers["Cache-Control"] = "public, max-age=15"
#                 return r  # neutralisé: hors fonction

            # Sinon on renvoie le même contenu + headers cache
            r = _StarResp(
                content=body,
                status_code=response.status_code,
                media_type=response.media_type,
                headers=dict(response.headers),
            )
            r.headers["ETag"] = etag
            r.headers["Cache-Control"] = "public, max-age=15"
#             return r  # neutralisé: hors fonction
        except Exception:
            # En cas de pépin, on renvoie la réponse originale
            return response


# --- Minimal health endpoint (added by script) ---
@app.get("/health")
def health():
    return {"ok": True}


@app.head("/healthz")
def healthz_head():
    return Response(status_code=200)

@app.head("/api/signals")
def signals_head() -> Response:
    # Réponse vide mais avec les bons headers pour permettre le caching côté frontend/proxy
    return Response(status_code=200, headers={
        "Cache-Control": "public, max-age=10",
        "Content-Type": "application/json"
    })
@app.get("/api/signals", response_model=None)
def api_signals(
    request: Request,
    response: Response,
    q: str = Query("", max_length=200, description="Recherche sur excerpt (ILIKE)"),
    sig_type: str | None = Query(None, description="Filtre sur type"),
    label: str | None = Query(None, description="Filtre sur label de feedback"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    where = []
    params = []

    if q:
        where.append("s.excerpt ILIKE %s")
        params.append(f"%{q}%")

    if sig_type:
        where.append("s.type = %s")
        params.append(sig_type)

    if label:
        where.append("EXISTS (SELECT 1 FROM signal_feedback f WHERE f.signal_id = s.id AND f.label = %s)")
        params.append(label)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    DB_URL = os.getenv("DB_URL", "postgresql://radar:radarpass@db:5432/radar")
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            # total pour pagination
            cur.execute(f"SELECT count(1) FROM signal s {where_sql};", params)
            total = int(cur.fetchone()[0])

            # page
            cur.execute(
                f"""
                SELECT s.id, s.type, s.event_date::text AS event_date, s.url, s.excerpt
                FROM signal s
                {where_sql}
                ORDER BY s.event_date DESC, s.id DESC
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            cols = [c[0] for c in cur.description]
            items = [dict(zip(cols, row)) for row in cur.fetchall()]

    payload = {
        "ok": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": (offset + limit) if (offset + limit) < total else None,
        "prev_offset": (offset - limit) if (offset - limit) >= 0 else None,
        "items": items,
    }
    headers = {"Cache-Control": "public, max-age=10"}
    response.headers.update(headers)
    return _json_with_cache(payload, headers=headers)


# --- Cache-Control pour /api/signals (GET & HEAD) ---

# --- Cache-Control pour /api/signals (GET, HEAD, OPTIONS) --- (version robuste)


# --- Tiny helper to attach Cache-Control on JSON payloads (no middleware) ---
def _json_with_cache(payload, max_age: int = 10, headers: dict | None = None):
    """Wrap JSONResponse with Cache-Control and optional extra headers."""
    base_headers = {"Cache-Control": f"public, max-age={max_age}"}
    if headers:
        base_headers.update(headers)
    return JSONResponse(payload, headers=base_headers)
