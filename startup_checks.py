import os

from dotenv import load_dotenv

load_dotenv()


REQUIRED = ["BOT_TOKEN"]


def validate_environment(require_bot_token: bool = True):
    missing = []
    if require_bot_token:
        for key in REQUIRED:
            if not os.getenv(key):
                missing.append(key)

    if missing:
        raise Exception(f"Missing env vars: {missing}")
