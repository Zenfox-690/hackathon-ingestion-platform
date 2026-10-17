import os

from fetcher.devfolio import parse_devfolio_cards_from_html
from fetcher.unstop import parse_unstop_cards_from_html


def test_devfolio_parser_excludes_navigation():
    # Synthetic HTML with navigation links and real hackathon cards
    synthetic_html = """
    <div>
        <a href="/hackathons/applied"><h3>Your hackathons</h3></a>
        <a href="/hackathons/upcoming"><h3>All upcoming hackathons</h3></a>
        <a href="https://devfolio.co/hackathons/past"><h3>All past hackathons</h3></a>
        <div class="HackathonCard__StyledCard-sc-1234">
            <a href="https://ai-summit-2026.devfolio.co/">
                <h3>AI Summit Hackathon</h3>
            </a>
            <p>Starts 15 Jun 2026</p>
        </div>
        <div class="HackathonCard__StyledCard-sc-1234">
            <a href="https://web3-build.devfolio.co/">
                <h3>Web3 Builders</h3>
            </a>
        </div>
    </div>
    """
    hackathons = parse_devfolio_cards_from_html(synthetic_html)
    assert len(hackathons) == 2

    titles = [h["name"] for h in hackathons]
    links = [h["link"] for h in hackathons]

    assert "Your hackathons" not in titles
    assert "All upcoming hackathons" not in titles
    assert "All past hackathons" not in titles
    assert "AI Summit Hackathon" in titles
    assert "Web3 Builders" in titles
    assert "https://ai-summit-2026.devfolio.co" in links


def test_unstop_parser_strips_countdown_timers():
    # Synthetic HTML with dynamic countdowns
    synthetic_html = """
    <div>
        <a href="/hackathons/ai-championship-1001">
            <h2>AI Championship 2026</h2>
            <div>Posted Jun 4, 2026</div>
            <div>6 days left</div>
        </a>
        <a href="/hackathons/code-clash-1002">
            <h3>Code Clash</h3>
            <div>13 hours left</div>
        </a>
    </div>
    """
    hackathons = parse_unstop_cards_from_html(synthetic_html)
    assert len(hackathons) == 2

    h1 = hackathons[0]
    h2 = hackathons[1]

    # Invariant: countdown text must not pollute the hackathon name
    assert "days left" not in h1["name"]
    assert "hours left" not in h2["name"]
    assert h1["name"] == "AI Championship 2026"
    assert h2["name"] == "Code Clash"
    assert h1["link"] == "https://unstop.com/hackathons/ai-championship-1001"


def test_cached_html_parsers_if_available():
    if os.path.exists("cache/devfolio.html"):
        with open("cache/devfolio.html", encoding="utf-8") as f:
            devfolio_items = parse_devfolio_cards_from_html(f.read(), limit=10)
        assert len(devfolio_items) > 0
        for item in devfolio_items:
            assert "your hackathons" not in item["name"].lower()
            assert "all upcoming hackathons" not in item["name"].lower()
            assert item["source"] == "Devfolio"
            assert item["link"].startswith("http")

    if os.path.exists("cache/unstop.html"):
        with open("cache/unstop.html", encoding="utf-8") as f:
            unstop_items = parse_unstop_cards_from_html(f.read(), limit=10)
        assert len(unstop_items) > 0
        for item in unstop_items:
            assert "days left" not in item["name"].lower()
            assert "hours left" not in item["name"].lower()
            assert item["source"] == "Unstop"
            assert item["link"].startswith("https://unstop.com/hackathons/")


def test_devpost_parser_synthetic_items():
    from fetcher.devpost import parse_devpost_items

    sample_items = [
        {
            "title": "  Global AI Innovation Challenge  ",
            "url": "https://global-ai.devpost.com/?ref=homepage",
            "submission_period_dates": "May 05 - Jun 11, 2026",
            "prize_amount": 50000,
            "themes": [{"name": "AI"}, {"name": "Machine Learning"}, "Education"],
            "displayed_location": {"location": "San Francisco, CA"},
        },
        {
            "title": "Online Open Hack",
            "url": "https://openhack.devpost.com",
            "submission_period_dates": "Unknown",
            "prize_amount": None,
            "themes": [],
            "displayed_location": None,
        },
    ]

    parsed = parse_devpost_items(sample_items)
    assert len(parsed) == 2

    p1 = parsed[0]
    assert p1["name"] == "Global AI Innovation Challenge"
    assert p1["link"] == "https://global-ai.devpost.com"
    assert p1["prize"] == "$50,000"
    assert "ai" in p1["tags"]
    assert "education" in p1["tags"]
    assert p1["location"] == "San Francisco, CA"
    assert p1["deadline"] == "2026-06-11T00:00:00"

    p2 = parsed[1]
    assert p2["name"] == "Online Open Hack"
    assert p2["location"] == "Online"
    assert p2["prize"] == "Unknown"
