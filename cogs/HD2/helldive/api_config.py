import os
from typing import Optional, Union

# pylint: disable=no-name-in-module
from pydantic import BaseModel, Field


class APIConfig(BaseModel):
    base_path: str = "https://api.helldivers2.dev"

    base_path_2: str = "https://api.diveharder.com"
    verify: Union[bool, str] = True
    client_name: str = "DefaultClientName"

    def get_access_token(self) -> Optional[str]:
        try:
            return os.environ["access_token"]
        except KeyError:
            return None

    def get_client_name(self):
        try:
            return self.client_name
        except KeyError:
            return None

    def set_access_token(self, value: str):
        raise Exception(
            "This client was generated with an environment variable for the access token. Please set the environment variable 'access_token' to the access token."
        )


class HTTPException(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"{status_code} {message}")

    def __str__(self):
        return f"{self.status_code} {self.message}"
