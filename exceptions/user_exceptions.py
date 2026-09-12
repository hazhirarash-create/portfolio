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
        