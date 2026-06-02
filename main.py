from fetcher.devpost import fetch_hackathons


hackathons = fetch_hackathons()

print(f"Fetched {len(hackathons)} hackathons\n")

for hackathon in hackathons[:5]:
    print(hackathon)
    print("-" * 50)