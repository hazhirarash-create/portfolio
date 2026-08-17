COMMON_PASSWORDS = {
    "password1234"
    "qwerty123456"
    "admin12345678"
    "password",
    "password123",
    "12345678",
    "123456789",
    "qwerty123",
    "admin123",
    "letmein",
}

def is_common_password(password: str) -> bool:
    candidate = password.strip().lower()
    return candidate in COMMON_PASSWORDS