from utils.dates import normalize_date


def test_normalize_single_date():
    assert normalize_date("Jun 11, 2026") == "2026-06-11T00:00:00"
    assert normalize_date("2026-06-11") == "2026-06-11T00:00:00"


def test_normalize_date_range_standard():
    # Devpost standard submission period range
    result = normalize_date("May 05 - Jun 11, 2026")
    assert result == "2026-06-11T00:00:00"

    result2 = normalize_date("May 19 - Aug 17, 2026")
    assert result2 == "2026-08-17T00:00:00"


def test_normalize_date_range_with_endash():
    result = normalize_date("Apr 15 – Jun 15, 2026")
    assert result == "2026-06-15T00:00:00"


def test_normalize_date_range_same_month():
    # Inherit month and year from range start
    result = normalize_date("Jun 01 - 15, 2026")
    assert result == "2026-06-15T00:00:00"


def test_normalize_iso_date():
    iso_date = "2026-06-11T12:00:00Z"
    result = normalize_date(iso_date)
    assert result is not None
    assert "2026" in result


def test_normalize_invalid_and_unknown():
    assert normalize_date("Unknown") is None
    assert normalize_date("unknown") is None
    assert normalize_date("") is None
    assert normalize_date(None) is None
    assert normalize_date("not-a-valid-date-string") is None
