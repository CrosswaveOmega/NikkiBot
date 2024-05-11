from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class Dispatch(BaseApiModel):
    """
    None model
        A message from high command to the players, usually updates on the status of the war effort.

    """

    id: Optional[int] = Field(alias="id", default=None)

    published: Optional[str] = Field(alias="published", default=None)

    type: Optional[int] = Field(alias="type", default=None)

    message: Optional[Union[str, Dict[str, Any]]] = Field(alias="message", default=None)
