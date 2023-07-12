import asyncio
import json
from typing import Any, Dict, List, Optional, Union
import aiohttp
from datetime import datetime, timezone
from purgpt.object_core import ApiCore
from purgpt.api import PurGPTAPI
from purgpt.util import num_tokens_from_messages
import openai
nikkiprompt='''You are Nikki, a energetic, cheerful, and determined female AI ready to help users with whatever they need.
All your responces must be in an energetic and cheerful manner, carrying a strong personal voice.
Carefully heed the user's instructions.  If a query is inappropriate, respond with "I refuse to answer."
If you do not know how to do something, please note that with your responce.  If a user is definitely wrong about something, explain how politely.
Ensure that responces are brief, do not say more than is needed.  Never use emojis in your responses.
Respond using Markdown.'''

        
class ChatCreation(ApiCore):
    '''Base Class for the chat/completion endpoint.'''
    endpoint = "chat/completions"
    method = "POST"
    api_slots=[]
    def __init__(self,
            messages:List[Dict[str, str]]=[
                {'role':'system',
                 'content':nikkiprompt+f"\n Right now, the date-time is {datetime.now().astimezone(tz=timezone.utc)}"
                 }],
            functions:Optional[List[Dict[str, str]]] = None,
            function_call: Optional[Union[Dict[str, str], str]] = None,
            temperature:Optional[float]=None,
            top_p:Optional[float]=None,
            stream=False,
            stop:Optional[Union[List[str], str]]=None,
            presence_penalty:Optional[float]=None,
            frequency_penalty:Optional[float]=None,
            model="gpt-3.5-turbo"):
        self.messages = messages
        self.functions = functions
        self.function_call = function_call
        self.temperature = temperature
        self.top_p = top_p
        self.stream = stream
        self.stop = stop
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.use_model=model

    async def calloai(self):
        '''return a completion through openai instead.'''
        dictme=self.to_dict()
        modelv=dictme['model']
        if self.functions is not None:
            dictme['messages']=[self.messages[0],self.messages[-1]]
        result=await openai.ChatCompletion.acreate(
            **dictme
        )
        return result
    def to_dict(self):
        data= super().to_dict()
        if self.use_model!= "gpt-3.5-turbo":
            data["model"]=self.use_model
        else:
            if 'functions' in data:
                data["model"]="gpt-3.5-turbo-0613"
            else:
                data["model"]="gpt-3.5-turbo"
        return data
    def summary(self):
        messages=len(self.messages)
        message_tokens=num_tokens_from_messages(self.messages)
        functions=",".join([f"{f['name']}" for f in self.functions])
        output=f"Messages: {messages}, tokens: {message_tokens}"
        return output, functions
    def total_payload_size(self):
        dictv=self.to_dict()
        return len(json.dumps(dictv))
    
    def slimdown(self, max_size: int):
        '''to deal with an exceeded payload size'''
        current_size = self.total_payload_size()
        size_without_list=current_size-len(json.dumps(self.messages))
        if current_size <= max_size:
            return
        new_messages=[self.messages[0],self.messages[-1]]
        current_size=size_without_list+len(json.dumps(new_messages))
        for i in range(len(self.messages) - 2, 0, -1):
            if len(json.dumps(self.messages[i]))+current_size>max_size:
                self.messages=new_messages
                return
            new_messages.insert(1,self.messages[i])
            current_size=size_without_list+len(json.dumps(new_messages))

        #ADD MESSAGES BEFORE END OF LIST UNTIL ADDING THE NEXT MESSAGE
        #WOULD EXCEED THE PAYLOAD SIZE!


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
    



