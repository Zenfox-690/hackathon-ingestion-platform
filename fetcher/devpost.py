import requests

from utils.dates import normalize_date


def fetch_hackathons():
    url = "https://devpost.com/api/hackathons"
    seen_links = set()

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] {e}")
        return []

    data = response.json()

    hackathons = []

    for item in data["hackathons"]:
        link = item["url"]

        if not link or link in seen_links:
            continue

        seen_links.add(link)

        hackathons.append({
            "name": item["title"],
            "description": "",
            "tags": [],
            "deadline": normalize_date(item.get("submission_period_dates")) or item.get("submission_period_dates"),
            "link": link,
            "source": "Devpost"
        })

    return hackathons