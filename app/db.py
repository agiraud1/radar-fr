import os
import psycopg
from pathlib import Path

DB_URL = os.getenv("DB_URL", "postgresql://radar:radarpass@db:5432/radar")
MODELS_PATH = Path(__file__).parent / "models.sql"

def init_db():
    sql = MODELS_PATH.read_text(encoding="utf-8")
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

if __name__ == "__main__":
    init_db()
    print("DB initialized.")
