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