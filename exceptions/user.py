class UsernameAlreadyExistsError(Exception):
    def __init__(self,username:str) -> None:
        self.username=username
        super().__init__(f"The username '{username}' already exists")


class EmailAlreadyExistsError(Exception):
    def __init__(self, email: str) -> None:
        self.email=email
        super().__init__(f"The email '{email}' is already registered")


class UserAlreadyExistsError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "A user with this username or email already exists"
        )


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