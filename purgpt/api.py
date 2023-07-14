import asyncio
from typing import Any, Dict, List, Optional, Union
import aiohttp
import json
import urllib
import purgpt
import openai
import openai.util as util
from purgpt.object_core import ApiCore
import purgpt.error as error
from assets import AssetLookup
BASE_URL='https://purgpt.xyz/v1'


'''rate limit:

{
"messages":[{"role":"user", "content":"Hello world, how are you doing?"}],
"key": "YOUR_API_KEY",
"model":"ANY DESIRED MODEL"
}
PurGPT Ratelimits

- 10 Requests per 10 seconds

- 2000 Requests per Day

'''
TIMEOUT_SECS=60*5
#Seconds until timeout.
MAX_LOAD_SIZE=20000
#Max payload size.
class PurGPTAPI:
    '''
    This bot utilizes the PurGPT api to connect to OpenAI.
    '''

    def __init__(self,token:str=None):
        self.base_url = BASE_URL
        
        
        
        if token!=None:
            if not isinstance(token, str):
                raise TypeError(f'expected token to be a str, received {token.__class__.__name__} instead')
            token = token.strip()
            self._key=token
        else:
            if purgpt.api_key==None:
                raise TypeError(f'expected set token to be a string, recieved {token.__class__.__name__} instead')
            self._key=purgpt.api_key
        self.openaimode=False
        
    async def _make_call(self,endpoint:str,payload:Dict[str,Any])->Dict[str,Any]:
        headers = {
            "Content-Type": "application/json"
        }
        data = payload
        print(data)
        if self._key==None: raise error.KeyException("API Key not set.")
        data['key']= self._key
        
        timeout = aiohttp.ClientTimeout(
                total=TIMEOUT_SECS
            )
        async with aiohttp.ClientSession() as session:
            print(f"{self.base_url}/{endpoint}")
            try:
                async with session.post(f"{self.base_url}/{endpoint}", headers=headers, json=data, timeout=timeout) as response:
                    if response.content_type== "application/json":
                        print(response)
                        result = await response.json()
                        print(result)
                        return result
                    else:
                        print(response.status,response.reason)
                        result=await response.text()
                        print(result)
                        #if 'err:' in result:  raise error.PurGPTError(f"{response.status}: {response.reason}", code=response.status)
                        raise error.PurGPTError(f"{response.status}: {response.reason}", code=response.status)
            except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as e:
                raise error.Timeout("Request timed out") from e
            except aiohttp.ClientError as e:
                raise error.APIConnectionError("AIO client error:",e) from e
            
    async def callapi(self,obj:ApiCore):
        if self.openaimode:
            return await obj.calloai()
        else:
            endpoint=obj.endpoint
            payload=obj.to_dict()
            if len(json.dumps(payload))>MAX_LOAD_SIZE:
                obj.slimdown(MAX_LOAD_SIZE)
                payload=obj.to_dict()

            response_dict= await self._make_call(endpoint,payload)
            openaiobject=util.convert_to_openai_object(response_dict)
            return openaiobject
    async def models(self):
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "key":self._key
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/models", headers=headers, json=data) as response:
                result = await response.json()
                return result

    def set_openai_mode(self,value:bool=False):
        self.openaimode=value

    async def check_oai(self,ctx):
        if ctx.bot.gptapi.openaimode:
            target_server=AssetLookup.get_asset('oai_server')
            if not ctx.guild:
                return True
            if ctx.guild.id!=int(target_server):
                await ctx.send("Only my owner may use the AI while OpenAI mode is on.", ephemeral=True)
                return True
            return False
        
    async def get_data(self, path):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/{path}") as response:
                data = await response.json()
                return data



