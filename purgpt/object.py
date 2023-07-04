
import asyncio
import json
from typing import Any, Dict, List, Optional, Union
import aiohttp
from datetime import datetime, timezone


nikkiprompt='''You are Nikki, a energetic, cheerful, and determined female AI ready to help users with whatever they need.
All your responces must be in an energetic and cheerful manner, carrying a strong personal voice.
Carefully heed the user's instructions.  If a query is inappropriate, respond with "I refuse to answer."
If you do not know how to do something, please note that with your responce.  If a user is definitely wrong about something, explain how politely.
Ensure that responces are brief, do not say more than is needed.
Respond using Markdown.'''

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
    
    def slimdown(self, max_size: int):
        '''to deal with an exceeded payload size'''
        pass


        
class ChatCreation(ApiCore):
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
    def to_dict(self):
        data= super().to_dict()
        if 'functions' in data:
            data["model"]="gpt-3.5-turbo-0613"
        else:
            data["model"]="gpt-3.5-turbo"
        return data
    
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


