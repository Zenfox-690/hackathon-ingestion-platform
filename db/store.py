import sqlite3


conn = sqlite3.connect("hackathons.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS hackathons (
    link TEXT PRIMARY KEY,
    name TEXT,
    deadline TEXT,
    source TEXT
)
""")

conn.commit()


def get_new_hackathons(hackathons):
    new_items = []

    for hackathon in hackathons:
        cursor.execute(
            "SELECT link FROM hackathons WHERE link = ?",
            (hackathon["link"],)
        )

        exists = cursor.fetchone()

        if not exists:
            cursor.execute(
                """
                INSERT INTO hackathons
                (link, name, deadline, source)
                VALUES (?, ?, ?, ?)
                """,
                (
                    hackathon["link"],
                    hackathon["name"],
                    hackathon["deadline"],
                    hackathon["source"]
                )
            )

            conn.commit()

            new_items.append(hackathon)

            print(f"[NEW] {hackathon['name']}")

    return new_items