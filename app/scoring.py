import os, datetime, psycopg

DB_URL = os.getenv("DB_URL", "postgresql://radar:radarpass@db:5432/radar")

# Recalcule le score par société pour une date donnée (UTC)
def recompute_daily(score_date: str | None = None) -> int:
    if not score_date:
        score_date = datetime.date.today().isoformat()

    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Aggrège les poids, prend le type dominant et une explication simple
            cur.execute("""
                with day_signals as (
                  select
                    s.company_id,
                    s.type,
                    sum(s.weight) as weight_sum,
                    count(*) as cnt
                  from signal s
                  where s.event_date = %s
                  group by 1,2
                ),
                per_company as (
                  select
                    company_id,
                    sum(weight_sum) as score_total,
                    -- type dominant = plus gros poids cumulé, tie-break par cnt
                    (array_agg(type order by weight_sum desc, cnt desc))[1] as top_type
                  from day_signals
                  group by company_id
                )
                insert into company_score_daily(company_id, score_date, score_total, top_signal_type, explanation)
                select
                  company_id,
                  %s::date,
                  score_total,
                  top_type,
                  'Somme pondérée des signaux du ' || %s::text
                from per_company
                on conflict (company_id, score_date) do update
                  set score_total = excluded.score_total,
                      top_signal_type = excluded.top_signal_type,
                      explanation = excluded.explanation
                returning company_id;
            """, (score_date, score_date, score_date))
            # rowcount = nb lignes insérées/MAJ
            return cur.rowcount
