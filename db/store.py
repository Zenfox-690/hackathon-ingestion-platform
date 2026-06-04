import hashlib
import sqlite3


conn = sqlite3.connect("hackathons.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS hackathons (
    fingerprint TEXT PRIMARY KEY,
    name TEXT,
    deadline TEXT,
    source TEXT,
    link TEXT
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    chat_id TEXT PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS filters (
    chat_id TEXT,
    keyword TEXT
)
""")
conn.commit()


def generate_fingerprint(hackathon):

    raw = (
        hackathon["name"].lower().strip()
        + hackathon["deadline"].lower().strip()
    )

    return hashlib.sha256(raw.encode()).hexdigest()


def get_new_hackathons(hackathons):

    new_items = []

    for hackathon in hackathons:

        fingerprint = generate_fingerprint(hackathon)

        cursor.execute(
            "SELECT fingerprint FROM hackathons WHERE fingerprint = ?",
            (fingerprint,)
        )

        exists = cursor.fetchone()

        if not exists:

            cursor.execute(
                """
                INSERT INTO hackathons
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    fingerprint,
                    hackathon["name"],
                    hackathon["deadline"],
                    hackathon["source"],
                    hackathon["link"]
                )
            )

            conn.commit()

            new_items.append(hackathon)

            print(f"[NEW] {hackathon['name']}")

    return new_items


def add_user(chat_id):

    cursor.execute(
        "INSERT OR IGNORE INTO users VALUES (?)",
        (str(chat_id),)
    )

    conn.commit()


def add_filter(chat_id, keyword):

    cursor.execute(
        """
        INSERT INTO filters
        (chat_id, keyword)
        VALUES (?, ?)
        """,
        (
            str(chat_id),
            keyword.lower()
        )
    )

    conn.commit()


def get_filters(chat_id):

    cursor.execute(
        """
        SELECT keyword
        FROM filters
        WHERE chat_id = ?
        """,
        (str(chat_id),)
    )

    rows = cursor.fetchall()

    return [row[0] for row in rows]


def get_users():

    cursor.execute(
        "SELECT chat_id FROM users"
    )

    rows = cursor.fetchall()

    return [row[0] for row in rows]