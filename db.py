import sqlite3

DB_NAME = "data.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        chat_id INTEGER,
        status TEXT DEFAULT 'UNKNOWN'
    )
    """)

    # На случай если таблица уже была создана без status
    try:
        c.execute("ALTER TABLE sites ADD COLUMN status TEXT DEFAULT 'UNKNOWN'")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def add_site(url, chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        "INSERT INTO sites (url, chat_id, status) VALUES (?, ?, ?)",
        (url, chat_id, "UNKNOWN")
    )

    conn.commit()
    conn.close()


def delete_site(url, chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("DELETE FROM sites WHERE url=? AND chat_id=?", (url, chat_id))

    conn.commit()
    conn.close()


def get_user_sites(chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT url, status FROM sites WHERE chat_id=?", (chat_id,))
    rows = c.fetchall()

    conn.close()
    return rows


def get_sites():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT id, url, chat_id, status FROM sites")
    rows = c.fetchall()

    conn.close()
    return rows


def update_site_status(site_id, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("UPDATE sites SET status=? WHERE id=?", (status, site_id))

    conn.commit()
    conn.close()