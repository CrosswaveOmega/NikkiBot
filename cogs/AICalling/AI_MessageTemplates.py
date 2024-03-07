from typing import Any, Optional
from discord import Embed, Color, Guild, GuildSticker, Message
from discord.ext import commands

from utility import MessageTemplates, get_server_icon_color
from bot import TCGuildTask
from assets import AssetLookup
from gptmod import ChatCreation
import gui

upper_ignore_limit = 50


class AIMessageTemplates(MessageTemplates):
    @staticmethod
    def get_invoke_audit_embed(
        message: Message, chat: Optional[ChatCreation] = None, color: int = 0xFFFFFF
    ):
        """Create an embed that sums up the server archive information for this server."""
        # add a message to the 'audit channel'
        emb = Embed(title="Audit", description=f"```{message.content}```")
        out, names = chat.summary()
        guild, user = message.guild, message.author
        emb.add_field(name="chat_summary", value=out[:1020], inline=False)
        if names:
            emb.add_field(name="Functions", value=names[:1020], inline=False)
        emb.add_field(name="chat_summary", value=f"choose: {str(chat.tool_choice)}")
        emb.add_field(
            name="Server Data",
            value=f"{guild.name}, \nServer ID: {guild.id}",
            inline=False,
        )
        emb.add_field(
            name="User Data", value=f"{user.name}, \n User ID: {user.id}", inline=False
        )
        return emb

    @staticmethod
    def get_response_audit_embed(
        message: Message, chat: Optional[Any] = None, color: int = 0xFFFFFF
    ):
        """Create an embed that sums up the server archive information for this server."""
        # add a message to the 'audit channel'
        emb = Embed(title="Audit", description=f"```{message.content[:4000]}```")
        if chat:
            if "model" in chat:
                emb.add_field(name="Model", value=chat["model"], inline=True)

            usage = chat.usage
            emb.add_field(name="Prompt", value=usage.prompt_tokens, inline=True)
            emb.add_field(name="Completion", value=usage.completion_tokens, inline=True)

        return emb

    @staticmethod
    def get_function_audit_embed(
        functiondict: dict,
        message: Message,
        name: Optional[str] = None,
        args: Optional[dict] = None,
    ):
        """Create an embed that sums up the server archive information for this server."""
        # add a message to the 'audit channel'
        guild, user = message.guild, message.author
        emb = Embed(title="Audit_FuncionCall", description=str(functiondict))
        emb.add_field(
            name="Server Data",
            value=f"{guild.name}, \nServer ID: {guild.id}",
            inline=False,
        )
        emb.add_field(
            name="User Data", value=f"{user.name}, \n User ID: {user.id}", inline=False
        )
        if name is not None and args is not None:
            emb.add_field(name="Function Call", value=f"{name}")
            bg = 0
            for an, av in args.items():
                emb.add_field(name=an, value=str(av), inline=True)
                bg += 1
                if bg >= 20:
                    break
        return emb

    @staticmethod
    async def add_resp_audit(
        ctx: commands.Context, message: Message, chat: Optional[Any] = None, **kwargs
    ):
        """Create an embed"""

        audit_channel = AssetLookup.get_asset("monitor_channel")
        if audit_channel:
            embed = AIMessageTemplates.get_response_audit_embed(message, chat)
            guild, user = ctx.guild, ctx.author
            embed.add_field(
                name="Server Data",
                value=f"{guild.name}, \nServer ID: {guild.id}",
                inline=False,
            )
            embed.add_field(
                name="User Data",
                value=f"{user.name}, \n User ID: {user.id}",
                inline=False,
            )
            target = ctx.bot.get_channel(int(audit_channel))
            message = await target.send(embed=embed)
            return message
        else:
            gui.gprint("No monitor channel detected in assets.")

    @staticmethod
    async def add_user_audit(
        ctx: commands.Context, chat: Optional[ChatCreation] = None, **kwargs
    ):
        """Create an embed"""

        audit_channel = AssetLookup.get_asset("monitor_channel")
        if audit_channel:
            embed = AIMessageTemplates.get_invoke_audit_embed(ctx.message, chat)
            target = ctx.bot.get_channel(int(audit_channel))
            message = await target.send(embed=embed)
            return message
        else:
            gui.gprint("No monitor channel detected in assets.")

    @staticmethod
    async def add_function_audit(
        ctx: commands.Context,
        functiondict: dict,
        name: Optional[str] = None,
        args: Optional[dict] = None,
    ):
        """Create an embed"""

        audit_channel = AssetLookup.get_asset("monitor_channel")
        if audit_channel:
            embed = AIMessageTemplates.get_function_audit_embed(
                functiondict, ctx.message, name, args
            )

            target = ctx.bot.get_channel(int(audit_channel))
            message = await target.send(embed=embed)
            return message
        else:
            gui.gprint("No monitor channel detected in assets.")
