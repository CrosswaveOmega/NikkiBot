import asyncio
from typing import Any, Dict, List, Optional, Union
import aiohttp
import json
import urllib
import purgpt
from purgpt.object import ApiCore,ChatCreation
import purgpt.error as error
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

Donators will have raised Limits

'''
TIMEOUT_SECS=120

class PurGPTAPI:
    '''
    This bot utilizes the PurGPT api to connect to OpenAI.
    '''
    def __init__(self,token:str=None):
        self.base_url = BASE_URL
        
        if not isinstance(token, str):
            raise TypeError(f'expected token to be a str, received {token.__class__.__name__} instead')
        token = token.strip()
        self._key=purgpt.api_key
        if token:
            self._key=token
        
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
                    result = await response.json()
                    print(result)
                    return result
            except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as e:
                raise error.Timeout("Request timed out") from e
            except aiohttp.ClientError as e:
                raise error.APIConnectionError("AIO client error:",e) from e
    async def callapi(self,obj:ApiCore):
        endpoint=obj.endpoint
        payload=obj.to_dict()
        return await self._make_call(endpoint,payload)
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

        
    async def get_data(self, path):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/{path}") as response:
                data = await response.json()
                return data


async def main():
    wrapper = PurGPTAPI(purgpt.api_key)
    mctx=ChatCreation(messages=[
            {'role':'user','content':'Say hello world'}
        ])
    response = await wrapper.callapi(mctx)
    print(response)
    result=response['choices']
    for i in result:
        print(i)
        print(i['message']['content'])
    print(response)

