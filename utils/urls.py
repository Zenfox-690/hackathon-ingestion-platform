from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def canonicalize_url(url: str) -> str:
    """Canonicalize a hackathon URL for consistent storage and deduplication.

    Normalizes scheme and host to lowercase, strips trailing slashes,
    removes tracking parameters (utm_*, ref, fbclid, etc.), and strips fragments.
    """
    if not url or not isinstance(url, str):
        return ""

    cleaned = url.strip()
    if not cleaned or cleaned.startswith(("#", "javascript:", "mailto:")):
        return ""

    lower_cleaned = cleaned.lower()
    if not (lower_cleaned.startswith("http://") or lower_cleaned.startswith("https://")):
        cleaned = "https://" + cleaned

    try:
        parsed = urlparse(cleaned)
        if not parsed.netloc or "." not in parsed.netloc:
            return ""
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        if netloc.endswith(":80") and scheme == "http":
            netloc = netloc[:-3]
        elif netloc.endswith(":443") and scheme == "https":
            netloc = netloc[:-4]

        # Strip trailing slashes from path
        path = parsed.path.rstrip("/")

        # Remove analytics / tracking query parameters
        query_params = parse_qsl(parsed.query, keep_blank_values=False)
        tracking_prefixes = ("utm_", "fbclid", "gclid", "ref", "source")
        clean_params = [(k, v) for k, v in query_params if not any(k.lower().startswith(p) for p in tracking_prefixes)]
        clean_query = urlencode(clean_params)

        res = urlunparse((scheme, netloc, path, "", clean_query, ""))
        return res.rstrip("/")
    except Exception:
        return cleaned.rstrip("/")
