import requests


def fetch_hackathons():
    url = "https://devpost.com/api/hackathons"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] {e}")
        return []

    data = response.json()

    hackathons = []

    for item in data["hackathons"]:
        hackathons.append({
            "name": item["title"],
            "deadline": item.get("submission_period_dates"),
            "link": item["url"],
            "source": "Devpost"
        })

    return hackathons