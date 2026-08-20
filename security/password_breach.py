import requests
import hashlib


def check_pwned_password(password: str) -> bool | None:

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
        return None