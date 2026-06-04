KEYWORDS = [
    "ai",
    "machine learning",
    "cybersecurity",
    "web3",
    "blockchain"
]


def matches_keywords(hackathon):

    text = hackathon["name"].lower()

    return any(keyword in text for keyword in KEYWORDS)