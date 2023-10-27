import asyncio
from typing import Any, Dict, List, Optional, Union
import aiohttp
import json
import urllib
import gptmod
import openai
import openai.util as util
from gptmod.object_core import ApiCore
import gptmod.error as error
from assets import AssetLookup


TIMEOUT_SECS = 60 * 10
# Seconds until timeout.
MAX_LOAD_SIZE = 40000


# Max payload size.
class GptmodAPI:
    """
    Simple GPT wrapper just in case.
    """

    def __init__(self, token: str = None):
        self.base_url = gptmod.base_url

        if token != None:
            if not isinstance(token, str):
                self._key = "None"
                self.openaimode = True
                # raise TypeError(f'expected token to be a str, received {token.__class__.__name__} instead')
            else:
                token = token.strip()
                self._key = token
                self.openaimode = False
        else:
            if gptmod.api_key == None:
                self._key = "None"
                self.openaimode = True
                # raise TypeError(f'expected set token to be a string, recieved {token.__class__.__name__} instead')
            else:
                self._key = gptmod.api_key
                self.openaimode = False

    async def _make_call(
        self, endpoint: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._key}",
        }
        data = payload
        # print(data)

        if self._key == None:
            raise error.KeyException("API Key not set.")
        # data['key']= self._key
        # print()
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECS)
        async with aiohttp.ClientSession() as session:
            print(f"{self.base_url}{endpoint}")
            try:
                async with session.post(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    json=data,
                    timeout=timeout,
                ) as response:
                    if response.content_type == "application/json":
                        print(response)
                        result = await response.json()
                        print(result)
                        return result
                    else:
                        print(response.status, response.reason)
                        result = await response.text()
                        print(result)
                        # if 'err:' in result:  raise error.GptmodError(f"{response.status}: {response.reason}", code=response.status)
                        raise error.GptmodError(
                            f"{response.status}: {response.reason}",
                            code=response.status,
                        )
            except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as e:
                raise error.Timeout("Request timed out") from e
            except aiohttp.ClientError as e:
                raise error.APIConnectionError("AIO client error:", e) from e

    async def callapi(self, obj: ApiCore):
        if self.openaimode:
            return await obj.calloai()
        else:
            if not self.base_url:
                raise error.GptmodError("There is no set base url.")
            endpoint = obj.endpoint
            payload = obj.to_dict(pro=True)
            if len(json.dumps(payload)) > MAX_LOAD_SIZE:
                obj.slimdown(MAX_LOAD_SIZE)
                payload = obj.to_dict(pro=True)

            response_dict = await self._make_call(endpoint, payload)
            openaiobject = util.convert_to_openai_object(response_dict)
            return openaiobject

    async def models(self):
        headers = {"Content-Type": "application/json"}
        data = {"key": self._key}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/models", headers=headers, json=data
            ) as response:
                result = await response.json()
                return result

    def set_openai_mode(self, value: bool = False):
        self.openaimode = value

    async def check_oai(self, ctx):
        if ctx.bot.gptapi.openaimode:
            target_server = AssetLookup.get_asset("oai_server")
            if not ctx.guild:
                return True
            if ctx.guild.id != int(target_server):
                await ctx.send(
                    "OpenAI mode may only be used in my private testing server.",
                    ephemeral=True,
                )
                return True
            return False

    async def get_data(self, path):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/{path}") as response:
                data = await response.json()
                return data
