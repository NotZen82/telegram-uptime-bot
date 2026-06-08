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
                CREATE TABLE IF NOT EXISTS chat_settings (
                    chat_id BIGINT PRIMARY KEY,
                    language TEXT DEFAULT 'ru'
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS sites (
                    id SERIAL PRIMARY KEY,
                    url TEXT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    status TEXT DEFAULT 'UNKNOWN',
                    ssl_alert_sent BOOLEAN DEFAULT FALSE,
                    failure_count INTEGER DEFAULT 0,
                    display_name TEXT,
                    failure_threshold INTEGER,
                    ssl_monitoring_enabled BOOLEAN DEFAULT TRUE,
                    domain_monitoring_enabled BOOLEAN DEFAULT TRUE,
                    check_interval_seconds INTEGER,
                    last_checked_at TIMESTAMP,
                    domain_alert_sent BOOLEAN DEFAULT FALSE,
                    domain_expires_at DATE,
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
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS display_name TEXT
            """)

            c.execute("""
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS failure_threshold INTEGER
            """)

            c.execute("""
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS ssl_monitoring_enabled BOOLEAN DEFAULT TRUE
            """)

            c.execute("""
                UPDATE sites
                SET ssl_monitoring_enabled = TRUE
                WHERE ssl_monitoring_enabled IS NULL
            """)

            c.execute("""
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS domain_monitoring_enabled BOOLEAN DEFAULT TRUE
            """)

            c.execute("""
                UPDATE sites
                SET domain_monitoring_enabled = TRUE
                WHERE domain_monitoring_enabled IS NULL
            """)

            c.execute("""
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS check_interval_seconds INTEGER
            """)

            c.execute("""
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMP
            """)

            c.execute("""
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS domain_alert_sent BOOLEAN DEFAULT FALSE
            """)

            c.execute("""
                ALTER TABLE sites
                ADD COLUMN IF NOT EXISTS domain_expires_at DATE
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
                SELECT url, status, display_name, domain_expires_at
                FROM sites
                WHERE chat_id=%s
                ORDER BY id
            """, (chat_id,))
            rows = c.fetchall()

    return [
        (row["url"], row["status"], row["display_name"])
        + (row["domain_expires_at"],)
        for row in rows
    ]


def get_user_site_by_number(chat_id, number):
    if number < 1:
        return None

    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT
                    id,
                    url,
                    chat_id,
                    status,
                    ssl_alert_sent,
                    failure_count,
                    display_name,
                    failure_threshold,
                    ssl_monitoring_enabled,
                    domain_monitoring_enabled,
                    check_interval_seconds,
                    last_checked_at,
                    domain_alert_sent,
                    domain_expires_at
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
                SELECT
                    id,
                    url,
                    chat_id,
                    status,
                    ssl_alert_sent,
                    failure_count,
                    display_name,
                    failure_threshold,
                    ssl_monitoring_enabled,
                    domain_monitoring_enabled,
                    check_interval_seconds,
                    last_checked_at,
                    domain_alert_sent,
                    domain_expires_at
                FROM sites
                WHERE chat_id=%s AND url=%s
            """, (chat_id, url))
            row = c.fetchone()

    return row


def get_sites():
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT
                    id,
                    url,
                    chat_id,
                    status,
                    ssl_alert_sent,
                    failure_count,
                    display_name,
                    failure_threshold,
                    ssl_monitoring_enabled,
                    domain_monitoring_enabled,
                    check_interval_seconds,
                    last_checked_at,
                    domain_alert_sent,
                    domain_expires_at
                FROM sites
                ORDER BY id
            """)
            rows = c.fetchall()

    return rows


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


def get_chat_language(chat_id):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT language FROM chat_settings WHERE chat_id=%s",
                (chat_id,)
            )
            row = c.fetchone()

    if not row:
        return None

    return row["language"]


def set_chat_language(chat_id, language):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO chat_settings (chat_id, language)
                VALUES (%s, %s)
                ON CONFLICT (chat_id)
                DO UPDATE SET language=EXCLUDED.language
            """, (chat_id, language))
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


def update_site_checked_at(site_id):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE sites SET last_checked_at=NOW() WHERE id=%s",
                (site_id,)
            )
        conn.commit()


def update_site_failure_threshold(site_id, threshold):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE sites SET failure_threshold=%s WHERE id=%s",
                (threshold, site_id)
            )
        conn.commit()


def update_site_ssl_monitoring(site_id, enabled):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                """
                UPDATE sites
                SET ssl_monitoring_enabled=%s, ssl_alert_sent=FALSE
                WHERE id=%s
                """,
                (enabled, site_id)
            )
        conn.commit()


def update_site_domain_monitoring(site_id, enabled):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                """
                UPDATE sites
                SET domain_monitoring_enabled=%s, domain_alert_sent=FALSE
                WHERE id=%s
                """,
                (enabled, site_id)
            )
        conn.commit()


def update_domain_alert_status(site_id, alert_sent):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE sites SET domain_alert_sent=%s WHERE id=%s",
                (alert_sent, site_id)
            )
        conn.commit()


def update_site_domain_expires_at(site_id, expires_at):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                """
                UPDATE sites
                SET domain_expires_at=%s, domain_alert_sent=FALSE
                WHERE id=%s
                """,
                (expires_at, site_id)
            )
        conn.commit()


def update_site_check_interval(site_id, interval_seconds):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE sites SET check_interval_seconds=%s WHERE id=%s",
                (interval_seconds, site_id)
            )
        conn.commit()


def update_site_display_name(site_id, display_name):
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE sites SET display_name=%s WHERE id=%s",
                (display_name, site_id)
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


