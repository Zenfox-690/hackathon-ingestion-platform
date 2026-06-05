from dateutil import parser


def normalize_date(date_text):

    if not date_text:
        return None

    try:
        parsed = parser.parse(
            date_text,
            fuzzy=True
        )

        return parsed.isoformat()

    except Exception:

        return None
