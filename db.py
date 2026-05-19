import os
import psycopg2
from psycopg2.extras import RealDictCursor


DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set")

    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


def init_db():
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS sites (
                    id SERIAL PRIMARY KEY,
                    url TEXT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    status TEXT DEFAULT 'UNKNOWN',
                    ssl_alert_sent BOOLEAN DEFAULT FALSE,
                    UNIQUE(url, chat_id)
                )
            """)

            c.execute("""
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS ssl_alert_sent BOOLEAN DEFAULT FALSE
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id SERIAL PRIMARY KEY,
                    site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE,
                    url TEXT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

        conn.commit()


def add_site(url, chat_id):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO sites (url, chat_id, status)
                VALUES (%s, %s, 'UNKNOWN')
                ON CONFLICT (url, chat_id) DO NOTHING
            """, (url, chat_id))
        conn.commit()


def delete_site(url, chat_id):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                "DELETE FROM sites WHERE url=%s AND chat_id=%s",
                (url, chat_id)
            )
        conn.commit()


def delete_site_by_number(chat_id, number):
    sites = get_user_sites(chat_id)

    if number < 1 or number > len(sites):
        return None

    url = sites[number - 1][0]
    delete_site(url, chat_id)

    return url


def get_user_sites(chat_id):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT url, status
                FROM sites
                WHERE chat_id=%s
                ORDER BY id
            """, (chat_id,))
            rows = c.fetchall()

    return [(row["url"], row["status"]) for row in rows]


def get_sites():
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, url, chat_id, status, ssl_alert_sent
                FROM sites
                ORDER BY id
            """)
            rows = c.fetchall()

    return [
        (
            row["id"],
            row["url"],
            row["chat_id"],
            row["status"],
            row["ssl_alert_sent"],
        )
        for row in rows
    ]


def site_exists(url, chat_id):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT id
                FROM sites
                WHERE url=%s AND chat_id=%s
            """, (url, chat_id))
            row = c.fetchone()

    return row is not None


def update_site_status(site_id, status):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE sites SET status=%s WHERE id=%s",
                (status, site_id)
            )
        conn.commit()


def update_ssl_alert_status(site_id, alert_sent):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE sites SET ssl_alert_sent=%s WHERE id=%s",
                (alert_sent, site_id)
            )
        conn.commit()


def add_incident(site_id, url, chat_id, status):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO incidents (site_id, url, chat_id, status)
                VALUES (%s, %s, %s, %s)
            """, (site_id, url, chat_id, status))
        conn.commit()


def get_user_incidents(chat_id, limit=10):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT url, status, created_at
                FROM incidents
                WHERE chat_id=%s
                ORDER BY created_at DESC
                LIMIT %s
            """, (chat_id, limit))
            rows = c.fetchall()

    return [
        (row["url"], row["status"], row["created_at"])
        for row in rows
    ]


