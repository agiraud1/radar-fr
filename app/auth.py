import os, time, psycopg
import jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("SECRET_KEY", "changeme")
ALGO = "HS256"
ACCESS_TOKEN_TTL = 60 * 60 * 24  # 24h

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB_URL = os.getenv("DB_URL", "postgresql://radar:radarpass@db:5432/radar")

def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_access_token(payload: dict, ttl: int = ACCESS_TOKEN_TTL) -> str:
    to_encode = payload.copy()
    to_encode["exp"] = int(time.time()) + ttl
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGO)

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGO])

def get_user_by_email(email: str):
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select id, client_id, full_name, email, password_hash, role
                from client_user where email=%s
            """, (email,))
            row = cur.fetchone()
            if not row:
                return None
            keys = ["id","client_id","full_name","email","password_hash","role"]
            return dict(zip(keys, row))

def get_user_by_id(user_id: int):
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select id, client_id, full_name, email, role
                from client_user where id=%s
            """, (user_id,))
            row = cur.fetchone()
            if not row: return None
            keys = ["id","client_id","full_name","email","role"]
            return dict(zip(keys, row))
