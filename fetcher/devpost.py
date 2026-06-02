import requests


def fetch_hackathons():
    url = "https://devpost.com/api/hackathons"

    response = requests.get(url)

    response.raise_for_status()

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