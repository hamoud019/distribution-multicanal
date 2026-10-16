"""The secret key of the pseudonymization (Part 6, section 3).

Every customer key, and every hash of an email or a phone, is a SHA-256 of the secret key followed by the
value. Without the key, nobody can recompute a customer key from a Shopify id or an email, even though those
ids are easy to guess. In production the key lives in the cloud key vault; in the proof of concept it is a
random key written once to poc/data/pseudonymization.key (never committed) and passed to dbt in the
LSF_POC_PSEUDONYMIZATION_KEY environment variable.
"""

import hashlib
import os
import secrets
from pathlib import Path

POC = Path(__file__).parent
KEY_FILE = POC / "data" / "pseudonymization.key"
ENV = "LSF_POC_PSEUDONYMIZATION_KEY"


def pseudonymization_key():
    """The key from the environment, else from the key file, created the first time."""
    if os.environ.get(ENV):
        return os.environ[ENV]
    if not KEY_FILE.exists():
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
    return KEY_FILE.read_text(encoding="utf-8").strip()


def pseudonymize(value, key=None):
    """The same hash as the dbt macro `pseudonymize`: SHA-256 of the key followed by the value, in hex."""
    return hashlib.sha256(((key or pseudonymization_key()) + value).encode("utf-8")).hexdigest()


def email_key(email, key=None):
    """The matching key of an email, as in staging: lower case, without the spaces around it."""
    return pseudonymize(email.strip().lower(), key) if email and email.strip() else None
