import asyncio
import json
from typing import Any, Dict, List, Optional, Union
import aiohttp
from datetime import datetime, timezone
from gptmod.object_core import ApiCore
from gptmod.api import GptmodAPI
from gptmod.util import num_tokens_from_messages
import openai


class ChatCreation(ApiCore):
    """Base Class for the chat/completion endpoint."""

    endpoint = "v1/chat/completions"
    method = "POST"
    api_slots = []

    def __init__(
        self,
        messages: Optional[List[Dict[str, str]]] = None,
        functions: Optional[List[Dict[str, str]]] = None,
        function_call: Optional[Union[Dict[str, str], str]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stream=False,
        stop: Optional[Union[List[str], str]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        tools: Optional[List[Dict[str, str]]] = None,
        tool_choice: Optional[Union[Dict[str, str], str]] = None,
        model="gpt-3.5-turbo",
    ):
        self.messages = []
        if messages is not None:
            self.messages = messages
        # self.functions = functions
        # self.function_call = function_call
        self.tools = tools
        self.tool_choice = tool_choice
        self.temperature = temperature
        self.top_p = top_p
        self.stream = stream
        self.stop = stop
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.use_model = model

    async def calloai(self, client):
        """return a completion through openai instead."""
        dictme = self.to_dict(pro=False)
        modelv = dictme["model"]
        # if self.functions is not None:  dictme['messages']=[self.messages[0],self.messages[-1]]
        result = await client.chat.completions.create(**dictme)
        return result

    def to_dict(self, pro=True):
        data = super().to_dict()
        data["model"] = "gpt-3.5-turbo-1106"
        return data

    def summary(self):
        messages = len(self.messages)
        message_tokens = num_tokens_from_messages(self.messages)
        functions = "none"
        if self.tools:
            functions = ",".join([f"{str(f['function']['name'])}" for f in self.tools])
        output = f"Messages: {messages}, tokens: {message_tokens}"
        return output, functions

    def total_payload_size(self):
        dictv = self.to_dict()
        return len(json.dumps(dictv))

    def slimdown(self, max_size: int):
        """to deal with an exceeded payload size"""
        current_size = self.total_payload_size()
        size_without_list = current_size - len(json.dumps(self.messages))
        if current_size <= max_size:
            return
        new_messages = [self.messages[0], self.messages[-1]]
        current_size = size_without_list + len(json.dumps(new_messages))
        for i in range(len(self.messages) - 2, 0, -1):
            if len(json.dumps(self.messages[i])) + current_size > max_size:
                self.messages = new_messages
                return
            new_messages.insert(1, self.messages[i])
            current_size = size_without_list + len(json.dumps(new_messages))

        # ADD MESSAGES BEFORE END OF LIST UNTIL ADDING THE NEXT MESSAGE
        # WOULD EXCEED THE PAYLOAD SIZE!

    def add_message(
        self,
        role: str,
        content: Optional[str] = None,
        name: Optional[str] = None,
        tool_calls: Optional[Dict[str, str]] = None,
    ):
        message = {"role": role}
        if tool_calls is not None:
            message["tool_calls"] = tool_calls
        if role == "assistant" and tool_calls is not None:
            message["tool_calls"] = tool_calls
        else:
            if content is None:
                raise ValueError(
                    "The content parameter is required for roles other than 'assistant'."
                )
            message["content"] = content

        if name is not None:
            message["name"] = name

        self.messages.append(message)
