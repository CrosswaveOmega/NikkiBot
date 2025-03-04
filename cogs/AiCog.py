from utility.globalfunctions import find_urls, prioritized_string_split
from .AICalling import AIMessageTemplates
from .StepCalculator import evaluate_expression
from gptfunctionutil import (
    GPTFunctionLibrary,
    AILibFunction,
    LibParam,
)
from typing import Any, Literal, Union
import discord
import gui
import io

import aiohttp
import asyncio
import re

# import datetime


from discord.ext import commands

from discord import app_commands
from utility import MessageTemplates, urltomessage
from utility.embed_paginator import pages_of_embeds
from bot import TCBot, TC_Cog_Mixin
import gptmod
import gptmod.error
from gptmod.sentence_mem import SentenceMemory, MemoryFunctions

from database.database_ai import AuditProfile, ServerAIConfig
from utility import split_string_with_code_blocks
import json

from database import Users_DoNotTrack

lock = asyncio.Lock()
JSONMODE = False
MEMORYMODE = False
nikkiprompt = """You are Nikki, a energetic, cheerful, and determined female AI ready to help users with whatever they need.
All your responses must convey a strong personal voice.  
Be as objective as possible.
Carefully heed the user's instructions.
If you do not know how to do something, please note that with your response.
[JSONMODE]
Never use emoji.
Respond using Markdown."""
json_prompt = """Respond with one JSON object with two fields, 'content' and 'new_memory'.
'content' will be what you will say to the user.
'new_memory' should be a list of strings, each 1-3 sentences long.  The strings in new_memory will be added to long term memory, and will be used to remember the chat context.
Ensure that responses are brief, do not say more than is needed.  """
memory_prompt = """The next system message will contain a memory bank, filled with sentences that are probably related to the user's messages.
Only your responses will be added to the memory bank, never the users.  
"""
reasons = {
    "server": {
        "messagelimit": "This server has reached the daily message limit, please try again tomorrow.",
        "ban": "This server is banned from using my AI due to repeated violations.",
        "cooldown": "There's a one minute delay between messages.",
        "disable": "The AI is disabled for new servers because of privacy concerns.",
    },
    "user": {
        "messagelimit": "You have reached the daily message limit, please try again tomorrow.",
        "ban": "You are forbidden from using my AI due to conduct.",
        "cooldown": "There's a one minute delay between messages, slow down man!",
        "disable": "The AI is disabled for new users because of privacy concerns.",
    },
}


class DummyMessage:
    def __init__(self, cont):
        self.content = cont


class MyLib(GPTFunctionLibrary):
    @AILibFunction(name="get_time", description="Get the current time and day in UTC.")
    @LibParam(comment="An interesting, amusing remark.")
    async def get_time(self, comment: str):
        # This is an example of a decorated coroutine command.
        return f"{comment}\n{str(discord.utils.utcnow())}"

    # pass


async def precheck_context(ctx: commands.Context) -> bool:
    """Evaluate if a message should be processed."""
    guild, user = ctx.guild, ctx.author

    async with lock:
        serverrep, userrep = AuditProfile.get_or_new(guild, user)
        serverrep.checktime()
        userrep.checktime()

        ok, reason = serverrep.check_if_ok()
        if not ok:
            await ctx.channel.send(
                f"<t:{int(serverrep.last_call.timestamp())}:F>,  <t:{int(serverrep.started_dt.timestamp())}:F>, {serverrep.current}, {serverrep.DailyLimit}"
            )
            await ctx.channel.send(reasons["server"][reason])
            return False
        ok, reason = userrep.check_if_ok()
        if not ok:
            if reason != "disable":
                await ctx.channel.send(reasons["user"][reason])
            return False
        serverrep.modify_status()
        userrep.modify_status()
    return True


async def process_result(
    ctx: commands.Context,
    result: Any,
    mylib: GPTFunctionLibrary,
    chat,
    mem: SentenceMemory = None,
    present_mem="",
):
    """
    process the result.  Will either send a message, or invoke a function.


    When a function is invoked, the output of the function is added to the chain instead.
    """
    gui.dprint()

    i = result.choices[0]

    role, content = i.message.role, i.message.content
    if content is not None:
        if JSONMODE:
            jsonout = await gptmod.errorous_json_decode(content, ctx.bot)
        else:
            jsonout = {"content": content, "new_memory": []}

    messageresp = None
    function = None
    finish_reason = i.finish_reason
    id = None
    toolcont = ""

    if finish_reason == "tool_calls" or i.message.tool_calls:
        # Call the corresponding funciton, and set that to content.
        function = str(i.message.tool_calls)
        chat.messages.append(
            {"role": role, "content": content, "tool_calls": i.message.tool_calls}
        )
        for tool_call in i.message.tool_calls:
            audit = await AIMessageTemplates.add_function_audit(
                ctx,
                tool_call,
                tool_call.function.name,
                json.loads(tool_call.function.arguments),
            )
            outcome = await mylib.call_by_tool_ctx(ctx, tool_call)

            contents = outcome["content"]
            if isinstance(contents, discord.Message):
                messageresp = contents
                contents = messageresp.content
                if mem:
                    await mem.add_to_mem(ctx, messageresp, present_mem=present_mem)

                return role, contents, messageresp, function

            toolcont = str(contents)

            chat.messages.append(
                {"role": "tool", "content": contents, "tool_call_id": tool_call.id}
            )
            audit = await AIMessageTemplates.add_resp_audit(
                ctx,
                DummyMessage(contents),
                chat,
            )

            chat.tools = None
            chat.tool_choice = None
            result2 = await ctx.bot.gptapi.callapi(chat)

            i2 = result2.choices[0]
            role, this_content = i2.message.role, i2.message.content
            if JSONMODE:
                jsonout = await gptmod.errorous_json_decode(this_content, ctx.bot)
            else:
                jsonout = {"content": this_content, "new_memory": []}
            content = this_content
            break

        # content = resp
    if isinstance(content, str):
        # Split up content by line if it's too long.
        mycontent = content
        page = commands.Paginator(prefix="", suffix=None)
        for p in content.split("\n"):
            page.add_line(p)
        split_by = split_string_with_code_blocks(mycontent, 2000)
        messageresp = None
        print(mycontent)
        for pa in split_by:
            ms = await ctx.channel.send(pa)
            if messageresp == None:
                messageresp = ms

        thiscont = f"{toolcont}\n{mycontent}"

        # await mem.add_list_to_mem(
        #     ctx, messageresp, jsonout["new_memory"], present_mem=present_mem
        # )
        if MEMORYMODE:
            chat.messages.append({"role": "assistant", "content": mycontent})
            memlib = MemoryFunctions()
            chat.tools = memlib.get_tool_schema()
            chat.tool_choice = {
                "type": "function",
                "function": {"name": "add_to_memory"},
            }
            res = await ctx.bot.gptapi.callapi(chat)

            for tool_call in res.choices[0].message.tool_calls:
                outcome = await memlib.call_by_tool_async(tool_call)
                contents, need = outcome["content"]
                print(contents, need)
                if need:
                    await mem.add_list_to_mem(
                        ctx, messageresp, cont=contents, present_mem=present_mem
                    )
    elif isinstance(content, discord.Message):
        messageresp = content
        content = messageresp.clean_content
        jsonout = {"content": messageresp.content, "new_memory": []}
    else:
        gui.dprint(result, content)
        messageresp = await ctx.channel.send("No output from this command.")
        content = "No output from this command."
    return role, content, messageresp, function


async def ai_message_invoke(
    bot: TCBot,
    message: discord.Message,
    mylib: GPTFunctionLibrary = None,
    thread_id=None,
):
    """Evaluate if a message should be processed."""

    permissions = message.channel.permissions_for(message.channel.guild.me)
    if permissions.send_messages:
        pass
    else:
        raise Exception(
            f"{message.channel.name}:{message.channel.id} send message permission not enabled."
        )
    if len(message.clean_content) > 2000:
        await message.channel.send("This message is too big.")
        return False
    ctx = await bot.get_context(message)
    if not bot.embedding():
        await message.channel.send("I'm still warming up!")
        return False
    if await ctx.bot.gptapi.check_oai(ctx):
        return

    botcheck = await precheck_context(ctx)
    if not botcheck:
        return
    guild, user = message.guild, message.author
    # Get the 'profile' of the active guild.
    profile = ServerAIConfig.get_or_new(guild.id)
    # prune message chains with length greater than X
    profile.prune_message_chains(limit=5, thread_id=thread_id)
    # retrieve the saved messages
    chain = profile.list_message_chains(thread_id=thread_id)
    # Convert into a list of messages
    mes = [c.to_dict() for c in chain]
    # create new ChatCreation
    chat = gptmod.ChatCreation(presence_penalty=0.3, messages=[])
    # ,model="gpt-4o-mini"
    np = nikkiprompt
    if JSONMODE:
        np = np.replace("[JSONMODE]", json_prompt)
    else:
        np = np.replace("[JSONMODE]", "")
    if MEMORYMODE:
        np = np.replace("[MEMORYMODE]", memory_prompt)
    else:
        np = np.replace("[MEMORYMODE]", "")

    chat.add_message("system", nikkiprompt)
    mem=None
    if MEMORYMODE:
        mem = SentenceMemory(ctx.bot, guild, user)
        docs, mems, alltime = await mem.search_sim(message)
        chat.add_message("system", name="memory", content=f"### MEMORY:\n{mems}")
        audit = await AIMessageTemplates.add_resp_audit(
            ctx,
            DummyMessage(mems),
            chat,
        )
    else:
        audit = await AIMessageTemplates.add_resp_audit(
            ctx,
            DummyMessage("."),
            chat,
        )
    for f in mes[:5]:  # Load old messags into ChatCreation
        chat.add_message(f["role"], f["content"])
    # Load current message into chat creation.
    chat.add_message("user", message.content)
    gui.dprint(len(chat.messages))
    # Load in functions
    forcecheck = None
    if mylib != None:
        forcecheck = mylib.force_word_check(message.content)
        if forcecheck:
            chat.tools = forcecheck
            chat.tool_choice = forcecheck[0]
        elif find_urls(message.content):
            chat.tools = mylib.get_tool_schema()
            chat.tool_choice = {"type": "function", "function": {"name": "read_url"}}
        else:
            pass
            # chat.tools = mylib.get_tool_schema()
            # chat.tool_choice = "auto"

    audit = await AIMessageTemplates.add_user_audit(ctx, chat)

    async with message.channel.typing():
        # Call the API.
        result = await bot.gptapi.callapi(chat)

    # only add messages after they're finished processing.

    bot.logs.info(str(result))
    # Process the result.
    role, content, messageresp, tools = await process_result(
        ctx, result, mylib, chat, mem, present_mem=mems
    )
    profile.add_message_to_chain(
        message.id,
        message.created_at,
        thread_id=thread_id,
        role="user",
        name=re.sub(r"[^a-zA-Z0-9_]", "", user.name),
        content=message.clean_content,
    )
    # Add
    if tools:
        profile.add_message_to_chain(
            messageresp.id,
            messageresp.created_at,
            thread_id=thread_id,
            role=role,
            content="",
            function=tools,
        )
    profile.add_message_to_chain(
        messageresp.id,
        messageresp.created_at,
        thread_id=thread_id,
        role=role,
        content=content,
    )

    audit = await AIMessageTemplates.add_resp_audit(ctx, messageresp, result)

    bot.database.commit()


async def download_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                return io.BytesIO(data)


class AICog(commands.Cog, TC_Cog_Mixin):
    """General commands"""

    def __init__(self, bot):
        self.helptext = "Currently disabled in non-testing servers."
        self.bot = bot
        self.init_context_menus()
        self.flib = MyLib()
        self.flib.do_expression = True
        self.flib.my_math_parser = evaluate_expression
        self.walked = False

    @commands.hybrid_group(fallback="view")
    @app_commands.default_permissions(manage_messages=True, manage_channels=True)
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, manage_channels=True)
    async def ai_setup(self, ctx):
        """This family of commands is for setting up the ai in your server."""
        guild = ctx.guild
        guildid = guild.id
        profile = ServerAIConfig.get_or_new(guildid)

        await MessageTemplates.server_ai_message(ctx, "Here is your server's data.")

    @ai_setup.command(name="clear_history", brief="clear ai chat history.")
    async def chear_history(self, ctx: commands.Context):
        guild = ctx.guild
        profile = ServerAIConfig.get_or_new(guild.id)
        thread_id = None
        if isinstance(ctx.channel, discord.Thread):
            thread_id = ctx.channel.id

        m1 = await MessageTemplates.server_ai_message(ctx, "purging")
        messages = profile.clear_message_chains(thread_id=thread_id)
        await m1.delete()
        await MessageTemplates.server_ai_message(ctx, f"{messages} purged")

    @commands.hybrid_command(
        name="ai_functions", description="Get a list of ai functions."
    )
    async def ai_functions(self, ctx):
        schema = self.flib.get_schema()

        def generate_embed(command_data):
            name = command_data["name"]
            description = command_data["description"]
            parameters = command_data["parameters"]["properties"]

            embed = discord.Embed(title=name, description=description)

            for param_name, param_data in parameters.items():
                param_fields = "\n".join(
                    [f"{key}: {value}" for key, value in param_data.items()]
                )
                embed.add_field(
                    name=param_name, value=param_fields[:1020], inline=False
                )
            return embed

        embeds = [generate_embed(command_data) for command_data in schema]
        if ctx.interaction:
            await pages_of_embeds(ctx, embeds, ephemeral=True)
        else:
            await pages_of_embeds(ctx, embeds)

    @commands.command(brief="Update user or server api limit [server,user],id,limit")
    @commands.is_owner()
    async def increase_limit(
        self, ctx, type: Literal["server", "user"], id: int, limit: int
    ):
        '''"Update user or server api limit `[server,user],id,limit`"'''
        if type == "server":
            profile = AuditProfile.get_server(id)
            if profile:
                profile.DailyLimit = limit
                self.bot.database.commit()
                await ctx.send("done")
            else:
                await ctx.send("server not found.")
        elif type == "user":
            profile = AuditProfile.get_user(id)
            if profile:
                profile.DailyLimit = limit
                self.bot.database.commit()
                await ctx.send("done")
            else:
                await ctx.send("user not found.")

    @commands.command(brief="Turn on OpenAI mode")
    @commands.is_owner()
    async def openai(self, ctx, mode: bool = False):
        self.bot.gptapi.set_openai_mode(mode)
        if mode == True:
            await ctx.send("OpenAI mode turned on.")
        if mode == False:
            await ctx.send("OpenAI mode turned off.")

    @commands.command(brief="Check memory")
    @commands.is_owner()
    async def memory_check(self, ctx, prompt: str):
        guild, user = ctx.guild, ctx.message.author
        mem = SentenceMemory(ctx.bot, guild, user)
        message = ctx.message
        message.content = prompt
        docs, str, alltimes = await mem.search_sim(message)
        splitorder = [
            "\n# %s",
            "\n## %s",
            "\n### %s",
            "\n#### %s",
            "\n##### %s",
            "\n###### %s",
            "%s\n",
            "%s.  ",
            "%s. ",
            "%s ",
        ]
        alltime, dtime, ltime = alltimes
        fil = prioritized_string_split(str, splitorder, default_max_len=1980)
        await ctx.send(f"took about {alltime.get_time()} seconds to gather neighbors.")
        await ctx.send(
            f"took about {dtime.get_time()} seconds to load into dictionary."
        )
        await ctx.send(
            f"took about {ltime.get_time()} seconds to sort into new_content"
        )
        for e, chunk in enumerate(fil):
            await ctx.send(chunk)

    @commands.command(brief="Dump memory")
    @commands.is_owner()
    async def memory_dump(self, ctx):
        guild, user = ctx.guild, ctx.message.author
        mem = SentenceMemory(ctx.bot, guild, user)
        message = ctx.message
        docs, str, alltimes = await mem.dump_memory(message)
        splitorder = [
            "\n# %s",
            "\n## %s",
            "\n### %s",
            "\n#### %s",
            "\n##### %s",
            "\n###### %s",
            "%s\n",
            "%s.  ",
            "%s. ",
            "%s ",
        ]
        alltime, dtime, ltime = alltimes

        fil = prioritized_string_split(str, splitorder, default_max_len=1980)
        await ctx.send(f"took about {alltime.get_time()} seconds to gather neighbors.")
        await ctx.send(
            f"took about {dtime.get_time()} seconds to load into dictionary."
        )
        await ctx.send(
            f"took about {ltime.get_time()} seconds to sort into new_content"
        )

        embs = []
        for e, chunk in enumerate(fil):
            embs.append(discord.Embed(title="memory dump", description=chunk))

        mess = await pages_of_embeds(ctx, embs)

    @commands.command(brief="Check memory")
    @commands.is_owner()
    async def memory_remove(self, ctx, url: str):
        guild, user = ctx.guild, ctx.message.author
        mem = SentenceMemory(ctx.bot, guild, user)
        message = ctx.message
        target = await urltomessage(url, ctx.bot)
        out = await mem.delete_message(url)
        await ctx.send("Removed url.")

    @commands.command(brief="add a sentence to memory")
    @commands.is_owner()
    async def memory_add(self, ctx, *, memory: str):
        guild, user = ctx.guild, ctx.message.author
        mem = SentenceMemory(ctx.bot, guild, user)
        message = ctx.message

        out = await mem.add_list_to_mem(ctx, message, [memory])
        await ctx.send("Memory added.")

    @commands.command(brief="clear user data")
    @commands.is_owner()
    async def memory_forget_user(self, ctx):
        guild, user = ctx.guild, ctx.message.author
        mem = SentenceMemory(ctx.bot, guild, user)
        message = ctx.message
        out = await mem.delete_user_messages(user.id)
        await ctx.send("Removed user memory.")

    @app_commands.command(name="ai_use", description="Check your current AI use.")
    async def usage(self, interaction: discord.Interaction) -> None:
        """check usage"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild, user = ctx.guild, ctx.author

        async with lock:
            serverrep, userrep = AuditProfile.get_or_new(guild, user)
            serverrep.checktime()
            userrep.checktime()

            await ctx.send(
                f"SERVER: <t:{int(serverrep.last_call.timestamp())}:F>, RESET ONL <t:{int(serverrep.started_dt.timestamp())}:F>, {serverrep.current}, {serverrep.DailyLimit}"
            )
            await ctx.send(
                f"USER: <t:{int(userrep.last_call.timestamp())}:F>, RESET ON<t:{int(userrep.started_dt.timestamp())}:F>, {userrep.current}, {userrep.DailyLimit}"
            )

        return True

    @app_commands.command(
        name="ban_user",
        description="Ban a user from using my AI.",
        extras={"homeonly": True},
    )
    @app_commands.describe(userid="user id")
    async def aiban(self, interaction: discord.Interaction, userid: str) -> None:
        """Ban a user from using the AI API."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        userid = int(userid)
        if interaction.user != self.bot.application.owner:
            await ctx.send("This command is owner only, buddy.")
            return
        profile = AuditProfile.get_user(userid)
        if profile:
            profile.ban()
            await ctx.send(f"Good riddance!  User <@{userid}> has been banned.")
        else:
            await ctx.send("I see no user by that name.")

    @app_commands.command(
        name="ban_server",
        description="Ban a server from using my AI.",
        extras={"homeonly": True},
    )
    @app_commands.describe(serverid="server id to ban.")
    async def aibanserver(
        self, interaction: discord.Interaction, serverid: str
    ) -> None:
        """Ban a entire server user using the AI API."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        serverid = int(serverid)
        if interaction.user != self.bot.application.owner:
            await ctx.send("This command is owner only, buddy.")
            return
        profile = AuditProfile.get_server(serverid)
        if profile:
            profile.ban()
            await ctx.send(f"Good riddance!  The server with id {id} has been banned.")
        else:
            await ctx.send("I see no server by that name.")

    @ai_setup.command(
        name="add_ai_channel",
        description="add a channel that Nikki will talk freely in.",
    )
    async def add_ai_channel(
        self, ctx, target_channel: Union[discord.TextChannel, discord.ForumChannel]
    ):
        "Add a channel that nikki can talk freely in"
        guild = ctx.guild
        guildid = guild.id
        profile = ServerAIConfig.get_or_new(guildid)
        chanment = [target_channel]
        if len(chanment) >= 1:
            for chan in chanment:
                profile.add_channel(chan.id)
        else:
            await MessageTemplates.server_ai_message(ctx, "?")
            return
        self.bot.database.commit()
        await MessageTemplates.server_ai_message(
            ctx,
            f"Understood.  Whenever a message is sent in <#{target_channel.id}>, I'll respond to it.",
        )

    @ai_setup.command(
        name="remove_ai_channel",
        description="use to stop Nikki from talking in an added AI Channel.",
    )
    @app_commands.describe(target_channel="channel to disable.")
    async def remove_ai_channel(
        self, ctx, target_channel: Union[discord.TextChannel, discord.ForumChannel]
    ):
        """remove a channel."""
        guild = ctx.guild
        guildid = guild.id
        profile = ServerAIConfig.get_or_new(guildid)
        chanment = [target_channel]
        if len(chanment) >= 1:
            for chan in chanment:
                profile.remove_channel(chan.id)
        else:
            await MessageTemplates.server_ai_message(ctx, "?")
            return
        self.bot.database.commit()
        await MessageTemplates.server_ai_message(
            ctx, "I will stop listening there, ok?  Pings will still work, though."
        )

    @commands.Cog.listener()
    async def on_raw_thread_delete(self, thread: discord.RawThreadDeleteEvent):
        try:
            profile = ServerAIConfig.get_or_new(thread.guild_id)
            thread_id = thread.thread_id
            messages = profile.clear_message_chains(thread_id=thread_id)
            gui.dprint("Purged.")
        except Exception as e:
            await self.bot.send_error(e)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listener that will invoke the AI upon a message."""
        if message.author.bot:
            return  # Don't respond to bot messages.
        if not message.guild:
            return  # Only work in guilds
        for p in self.bot.command_prefix:
            if message.content.startswith(p):
                return
        try:
            if not self.walked:
                self.flib.add_in_commands(self.bot)

            if Users_DoNotTrack.check_entry(message.author.id):
                return
            profile = ServerAIConfig.get_or_new(message.guild.id)
            thread_id = None
            targetid = message.channel.id
            thread_id = None
            if isinstance(message.channel, discord.Thread):
                targetid = message.channel.parent.id
                thread_id = message.channel.id
            if self.bot.user.mentioned_in(message) and not message.mention_everyone:
                if self.bot.gptapi.check_oai_silent(message.guild):
                    return
                if isinstance(message.channel, discord.Thread):
                    thread_id = message.channel.id
                await ai_message_invoke(
                    self.bot, message, mylib=self.flib, thread_id=thread_id
                )
            else:
                if profile.has_channel(targetid):
                    await ai_message_invoke(
                        self.bot, message, mylib=self.flib, thread_id=thread_id
                    )
        except Exception as error:
            try:
                emb = MessageTemplates.get_error_embed(
                    title="Error with your query!", description=str(error)
                )
                await message.channel.send(embed=emb)
            except Exception as e:
                try:
                    myperms = message.guild.system_channel.permissions_for(
                        message.guild.me
                    )
                    if myperms.send_messages:
                        await message.guild.system_channel.send(
                            "I need to be able to send messages in a channel to use this feature."
                        )
                except e:
                    pass

                await self.bot.send_error(
                    e, title="Could not send message", uselog=True
                )
            await self.bot.send_error(error, title="AI Responce error", uselog=True)


async def setup(bot):
    from .AICalling import setup

    await bot.load_extension(setup.__module__)
    await bot.add_cog(AICog(bot))


async def teardown(bot):
    from .AICalling import setup

    await bot.unload_extension(setup.__module__)
    await bot.remove_cog("AICog")
