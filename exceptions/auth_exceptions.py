class InvalidCredentialsError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Invalid username or password"
        )


class InactiveUserError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "User account is inactive"
        )

class InvalidTokenError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Could not validate credentials"
        )

class RefreshTokenReuseDetectedError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Refresh token reuse detected"
        )

class AdminAccessRequiredError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Admin access required"
        )

class CompromisedPasswordError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "This password is not allowed. Please choose another password."
        )