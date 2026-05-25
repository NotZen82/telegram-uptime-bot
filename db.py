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
                    failure_count INTEGER DEFAULT 0,
                    UNIQUE(url, chat_id)
                )
            """)

            c.execute("""
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS ssl_alert_sent BOOLEAN DEFAULT FALSE
            """)

            c.execute("""
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS failure_count INTEGER DEFAULT 0
            """)

            c.execute("""
                UPDATE sites
                SET failure_count = 0
                WHERE failure_count IS NULL
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

            c.execute("""
                ALTER TABLE incidents
                ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP
            """)

            c.execute("""
                ALTER TABLE incidents
                ADD COLUMN IF NOT EXISTS duration_seconds INTEGER
            """)

        conn.commit()
        
        
def open_incident(site_id, url, chat_id, status):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO incidents (site_id, url, chat_id, status)
                VALUES (%s, %s, %s, %s)
            """, (site_id, url, chat_id, status))
        conn.commit()


def close_incident(site_id):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                UPDATE incidents
                SET
                    resolved_at = NOW(),
                    duration_seconds = EXTRACT(EPOCH FROM (NOW() - created_at))::INTEGER,
                    status = 'RESOLVED'
                WHERE id = (
                    SELECT id
                    FROM incidents
                    WHERE site_id=%s
                      AND resolved_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                RETURNING duration_seconds
            """, (site_id,))

            row = c.fetchone()

        conn.commit()

    if not row:
        return None

    return row["duration_seconds"]


def format_duration(seconds):
    if seconds is None:
        return "unknown"

    seconds = int(seconds)

    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}h {minutes}m {sec}s"

    if minutes:
        return f"{minutes}m {sec}s"

    return f"{sec}s"


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


def get_user_site_by_number(chat_id, number):
    if number < 1:
        return None

    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, url, chat_id, status, ssl_alert_sent, failure_count
                FROM sites
                WHERE chat_id=%s
                ORDER BY id
                OFFSET %s
                LIMIT 1
            """, (chat_id, number - 1))
            row = c.fetchone()

    return row


def get_user_site_detail(chat_id, url):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, url, chat_id, status, ssl_alert_sent, failure_count
                FROM sites
                WHERE chat_id=%s AND url=%s
            """, (chat_id, url))
            row = c.fetchone()

    return row


def get_sites():
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, url, chat_id, status, ssl_alert_sent, failure_count
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
            row["failure_count"],
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


def update_failure_count(site_id, failure_count):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE sites SET failure_count=%s WHERE id=%s",
                (failure_count, site_id)
            )
        conn.commit()


def reset_failure_count(site_id):
    update_failure_count(site_id, 0)


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


def get_last_site_incident(chat_id, url):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT status, created_at, resolved_at, duration_seconds
                FROM incidents
                WHERE chat_id=%s AND url=%s
                ORDER BY created_at DESC
                LIMIT 1
            """, (chat_id, url))
            row = c.fetchone()

    return row


