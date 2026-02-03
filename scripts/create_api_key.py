"""
Dev utility: generate an API key and insert it into the database.

This script prints the plaintext API key once.
Store it securely; it cannot be recovered.
"""

import argparse
import secrets
import hashlib

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from urlshortenerapi.core.config import settings
from urlshortenerapi.db.models import ApiKey


def generate_api_key() -> str:
    return "sk_dev_" + secrets.token_urlsafe(32)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="dev")
    args = parser.parse_args()

    raw = generate_api_key()
    key_hash = hash_api_key(raw)

    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        row = ApiKey(name=args.name, key_hash=key_hash)
        session.add(row)
        session.commit()

    print("API key (store this now; it will not be shown again):")
    print(raw)


if __name__ == "__main__":
    main()
