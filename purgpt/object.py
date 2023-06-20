
import asyncio
from typing import Any, Dict, List, Optional, Union
import aiohttp




class ApiCore(dict):
    endpoint = None
    method = None

    def __init__(self):
        pass

    @classmethod
    def create(cls, **kwargs):
        instance = cls()
        for key, value in kwargs.items():
            setattr(instance, key, value)
        return instance

    def to_dict(self):
        serialized_dict = {}
        for key, value in self.__dict__.items():
            if key not in ["endpoint", "method"]:
                if value is not None:
                    print(key,value)
                    serialized_dict[key] = value
        return serialized_dict



class ChatCreation(ApiCore):
    endpoint = "chat/completions"
    method = "POST"
    api_slots=[]
    def __init__(self,
            messages:List[Dict[str, str]]=[],
            functions:Optional[List[Dict[str, str]]] = None,
            function_call: Optional[Union[Dict[str, str], str]] = None,
            temperature:Optional[float]=None,
            top_p:Optional[float]=None,
            stream=False,
            stop:Optional[Union[List[str], str]]=None,
            presence_penalty:Optional[float]=None,
            frequency_penalty:Optional[float]=None):
        self.messages = messages
        self.functions = functions
        self.function_call = function_call
        self.temperature = temperature
        self.top_p = top_p
        self.stream = stream
        self.stop = stop
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty

    def add_message(
        self,
        role: str,
        content: Optional[str] = None,
        name: Optional[str] = None,
        function_call: Optional[Dict[str, str]] = None,
    ):
        message = {"role": role}
        if function_call is not None:
            message["function_call"] = function_call
        if role == "assistant" and function_call is not None:
            message["function_call"] = function_call
        else:
            if content is None:
                raise ValueError("The content parameter is required for roles other than 'assistant'.")
            message["content"] = content

        if name is not None:
            message["name"] = name

        self.messages.append(message)

