from utils.urls import canonicalize_url


def test_canonicalize_url_trailing_slash():
    url1 = "https://rapid-agent.devpost.com/"
    url2 = "https://rapid-agent.devpost.com"
    assert canonicalize_url(url1) == "https://rapid-agent.devpost.com"
    assert canonicalize_url(url1) == canonicalize_url(url2)


def test_canonicalize_url_tracking_params():
    clean = "https://unstop.com/hackathons/my-hackathon-123"
    dirty = "https://unstop.com/hackathons/my-hackathon-123/?utm_source=telegram&utm_medium=bot&ref=share"
    assert canonicalize_url(dirty) == clean


def test_canonicalize_url_scheme_and_netloc_lowercase():
    mixed = "HTTPS://DEVPOST.COM/hackathons/test"
    assert canonicalize_url(mixed) == "https://devpost.com/hackathons/test"


def test_canonicalize_url_invalid_or_fragments():
    assert canonicalize_url("#main-content") == ""
    assert canonicalize_url("javascript:void(0)") == ""
    assert canonicalize_url("") == ""
    assert canonicalize_url(None) == ""
