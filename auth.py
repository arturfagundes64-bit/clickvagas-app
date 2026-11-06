import base64
import hashlib
import hmac
import os

_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ROUNDS = 200_000


def hash_password(password):
    """Return a salted PBKDF2 hash, rather than storing a readable password."""
    if password.startswith(f"{_PASSWORD_SCHEME}$"):
        return password
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PASSWORD_ROUNDS)
    return "$".join(
        (
            _PASSWORD_SCHEME,
            str(_PASSWORD_ROUNDS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password, stored):
    if not stored:
        return False
    if not stored.startswith(f"{_PASSWORD_SCHEME}$"):
        # Aceita credenciais em texto simples apenas durante a migração dos dados antigos.
        return hmac.compare_digest(password, stored)
    try:
        scheme, rounds, salt_text, digest_text = stored.split("$", 3)
        if scheme != _PASSWORD_SCHEME:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
