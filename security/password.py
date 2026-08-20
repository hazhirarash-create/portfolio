from pwdlib import PasswordHash
import hashlib
import requests


password_hash = PasswordHash.recommended()

DUMMY_PASSWORD_HASH = password_hash.hash(
    "dummy-password-for-timing"
)

def is_pwned_password(password: str) -> bool:

    password_hash = hashlib.sha1(
        password.encode("utf-8")
    ).hexdigest().upper()

    prefix = password_hash[:5]
    suffix = password_hash[5:]

    url = (
        "https://api.pwnedpasswords.com/range/"
        f"{prefix}"
    )

    try:
        response = requests.get(
            url,
            timeout=3
        )

        response.raise_for_status()

        for line in response.text.splitlines():
            returned_suffix, _count = line.split(":", 1)

            if returned_suffix == suffix:
                return True

        return False

    except requests.RequestException:
        return False


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password
    )