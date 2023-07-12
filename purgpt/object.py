
import asyncio
import json
from typing import Any, Dict, List, Optional, Union
import aiohttp
from datetime import datetime, timezone
from purgpt.object_core import ApiCore
from purgpt.api import PurGPTAPI
from purgpt.util import num_tokens_from_messages
import openai


class Edit(ApiCore):
    endpoint = "edits"
    method = "POST"
    api_slots=[]
    def __init__(self,
            model:str,
            input:str,
            instruction: str,
            n:Optional[int]=None,
            temperature:Optional[float]=None,
            top_p:Optional[float]=None):
        self.model:str = model,
        self.input = input
        self.instruction = instruction
        self.n=n
        self.temperature = temperature
        self.top_p = top_p
    def to_dict(self):
        dictv={
            'model':'text-davinci-edit-001',
            'input':self.input,
            'instruciton':self.instruction
        }
        return dictv


