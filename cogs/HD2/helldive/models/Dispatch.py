from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel
import discord


import re



# Define the regex pattern to match <i=1>...</i> tags
pattern = r'<i=1>(.*?)<\/i>'
pattern3 = r'<i=3>(.*?)<\/i>'



class Dispatch(BaseApiModel):
    """
    None model
        A message from high command to the players, usually updates on the status of the war effort.

    """

    id: Optional[int] = Field(alias="id", default=None)

    published: Optional[str] = Field(alias="published", default=None)

    type: Optional[int] = Field(alias="type", default=None)

    message: Optional[Union[str, Dict[str, Any]]] = Field(alias="message", default=None)

    def to_embed(self):
        #message=self.# Replace the matched patterns with markdown bold syntax
        converted_text = re.sub(pattern, r'**\1**', self.message)
        converted_text = re.sub(pattern3, r'***\1***', converted_text)
        return discord.Embed(
            title=f"Dispatch {self.id}, type {self.type}",
            description=f"{converted_text}\n{self.published}",
        )
