REQUIRED_KEYS = {
    "name",
    "deadline",
    "prize",
    "link",
    "source"
}


def validate_hackathon(data):

    return REQUIRED_KEYS.issubset(data.keys())