from auth import hash_password
import psycopg, os

DB_URL = os.getenv("DB_URL", "postgresql://radar:radarpass@db:5432/radar")

def run():
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            # client de démo
            cur.execute("""
                insert into client (name, sector_focus, email_primary, alert_threshold, is_active)
                values ('Client Démo', 'Industrie;Services B2B', 'demo@example.com', 75, true)
                on conflict do nothing
                returning id;
            """)
            row = cur.fetchone()
            client_id = row[0] if row else 1  # si déjà présent

            # admin de démo
            email = "admin@demo.local"
            password_hash = hash_password("demo1234")
            cur.execute("""
                insert into client_user (client_id, full_name, email, password_hash, role)
                values (%s, 'Admin Démo', %s, %s, 'admin')
                on conflict (email) do nothing;
            """, (client_id, email, password_hash))

if __name__ == "__main__":
    run()
    print("Seed OK: admin=admin@demo.local / pass=demo1234")
