REQUIRED_KEYS = {
    "name",
    "description",
    "tags",
    "deadline",
    "prize",
    "link",
    "source"
}


def validate_hackathon(data):

    return REQUIRED_KEYS.issubset(data.keys())