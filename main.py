from fetcher.devfolio import DevfolioFetcher


fetcher = DevfolioFetcher()

try:
    hackathons = fetcher.fetch()

except Exception as e:
    print(f"[ERROR] {e}")

    hackathons = []

print(f"\nFetched: {len(hackathons)}\n")

for hackathon in hackathons:
    print(hackathon)
    print("-" * 50)