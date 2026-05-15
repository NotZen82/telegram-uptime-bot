import sqlite3

DB_NAME = "data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        chat_id INTEGER
    )
    """)

    conn.commit()
    conn.close()


def add_site(url, chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("INSERT INTO sites (url, chat_id) VALUES (?, ?)", (url, chat_id))

    conn.commit()
    conn.close()


def get_sites():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT url, chat_id FROM sites")
    rows = c.fetchall()

    conn.close()
    return rows


def delete_site(url, chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("DELETE FROM sites WHERE url=? AND chat_id=?", (url, chat_id))

    conn.commit()
    conn.close()

def get_user_sites(chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT url FROM sites WHERE chat_id=?", (chat_id,))
    rows = c.fetchall()

    conn.close()
    return rows


def get_user_sites(chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT url FROM sites WHERE chat_id=?", (chat_id,))
    rows = c.fetchall()

    conn.close()
    return rows