import os

from dotenv import load_dotenv


load_dotenv()


REQUIRED = [
    "BOT_TOKEN"
]


def validate_environment():

    missing = []

    for key in REQUIRED:

        if not os.getenv(key):

            missing.append(key)

    if missing:

        raise Exception(
            f"Missing env vars: {missing}"
        )