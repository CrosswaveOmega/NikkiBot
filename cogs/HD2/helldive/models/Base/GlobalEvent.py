from typing import *
import datetime
from pydantic import Field
from ..ABC.model import BaseApiModel, HealthMixin


class GlobalEvent(BaseApiModel):
    """
    None model
        An ongoing global event.

    """

    eventId: Optional[int] = Field(alias="eventId", default=None)

    id32: Optional[int] = Field(alias="id32", default=None)
    portraitId32: Optional[int] = Field(alias="portraitId32", default=None)
    title: Optional[str] = Field(alias="title", default=None)
    titleId32: Optional[int] = Field(alias="titleId32", default=None)
    message: Optional[str] = Field(alias="message", default=None)
    messageId32: Optional[int] = Field(alias="messageId32", default=None)
    introMediaId32: Optional[int] = Field(
        alias="introMediaId32", default=None, description="Use currently unknown."
    )
    outroMediaId32: Optional[int] = Field(
        alias="outroMediaId32", default=None, description="Use currently unknown."
    )
    race: Optional[int] = Field(alias="race", default=None)
    flag: Optional[int] = Field(alias="flag", default=None)
    assignmentId32: Optional[int] = Field(alias="assignmentId32", default=None)
    effectIds: Optional[List[int]] = Field(alias="effectIds", default_factory=list)
    planetIndices: Optional[List[int]] = Field(
        alias="planetIndices", default_factory=list
    )

    def strout(self) -> str:
        formatv = {
            k: v
            for k, v in self.model_dump().items()
            if k not in ["message", "title", "retrieved_at"]
        }

        return ", ".join([f"{k}:`{v}`" for k, v in formatv.items()])
