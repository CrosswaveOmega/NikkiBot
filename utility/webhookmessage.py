from random import randint, choice
import re
from typing import List, Tuple, Union
import discord
import gui
import aiohttp
from discord import Webhook

default_webhook_name = "BotHook"


class WebhookMessageWrapper:
    @staticmethod
    async def postwebhookcopy_channel(
        channel, message: discord.Message, embeds=List[discord.Embed]
    ) -> discord.WebhookMessage:
        content = message.content
        name = message.author.name
        avatar = message.author.avatar

        if avatar != None:
            avatar = str(avatar)
        files = []
        for attach in message.attachments:
            # Retrieve files.W
            this_file = await attach.to_file()
            files.append(this_file)
        return await WebhookMessageWrapper.postWebhookMessageProxy(
            channel,
            message_content=content,
            display_username=name,
            avatar_url=avatar,
            embed=embeds,
            file=files,
        )

    @staticmethod
    async def postCopyWithWebhook(
        webhook,
        thread,
        message: discord.Message,
        embeds=List[discord.Embed],
        noauthor=False,
    ) -> discord.WebhookMessage:
        content = message.content
        name = message.author.name
        avatar = message.author.avatar
        if avatar != None:
            avatar = avatar.url
        files = []
        if noauthor:
            avatar = None
            name = choice(
                [
                    "alpha",
                    "beta",
                    "gamma",
                    "delta",
                    "epsilon",
                    "zeta",
                    "eta",
                    "theta",
                    "iota",
                    "kappa",
                    "lambda",
                    "mu",
                    "nu",
                    "xi",
                    "omicron",
                    "pi",
                    "rho",
                    "sigma",
                    "tau",
                    "upsilon",
                    "phi",
                    "chi",
                    "psi",
                    "omega",
                ]
            )
        for attach in message.attachments:
            # Retrieve files.
            this_file = await attach.to_file()
            files.append(this_file)

        return await WebhookMessageWrapper.postMessageWithWebhook(
            webhook,
            thread,
            message_content=content,
            display_username=name,
            avatar_url=avatar,
            embed=embeds,
            file=files,
        )

    @staticmethod
    async def postMessageAsWebhookWithURL(
        webhookurl, thread=None, **kwargs
    ) -> discord.WebhookMessage:
        """posts a message as a webhook"""

        webhook = None
        async with aiohttp.ClientSession() as session:
            webhook = Webhook.from_url(webhookurl, session=session)

            mess = await WebhookMessageWrapper.postMessageWithWebhook(
                webhook, thread, **kwargs
            )
            return mess

    @staticmethod
    async def getWebhookInChannel(
        text_channel: discord.TextChannel,
    ) -> Tuple[discord.Webhook, Union[discord.Thread, None]]:
        thread = None
        tlist = [
            discord.ChannelType.news_thread,
            discord.ChannelType.public_thread,
            discord.ChannelType.private_thread,
        ]
        if text_channel.type in tlist:
            thread = text_channel
            text_channel = thread.parent
        webhooks = await text_channel.webhooks()
        webhook = None
        for web in webhooks:
            if web.token != None:
                webhook = web
        if webhook == None:
            # Make a new webhook.
            fp = open("./assets/defaultwebhookavatar.png", "rb")
            fp.seek(0)
            pfp = fp.read()
            newname = f"{default_webhook_name}_" + text_channel.name[:40]
            webhook = await text_channel.create_webhook(
                name=newname,
                avatar=pfp,
                reason="So proxy messages can be sent in this channel.",
            )
            fp.close()
        return webhook, thread

    @staticmethod
    async def postMessageWithWebhook(
        webhook,
        thread,
        message_content,
        display_username=None,
        avatar_url=None,
        embed=[],
        file=[],
    ) -> discord.WebhookMessage:
        if not message_content and not file and not embed:
            gui.gprint("No content, no file, and no embed.")
            return None
        if message_content.isspace() and not file and not embed:
            gui.gprint("Empty,no file, and no embed.")
            return None
        if display_username:
            display_username = re.sub(
                "discord", "Captain", display_username, flags=re.IGNORECASE
            )
        newContent = message_content
        mess = None
        try:
            if thread != None:
                mess = await webhook.send(
                    content=newContent,
                    username=display_username,
                    avatar_url=avatar_url,
                    embeds=embed,
                    files=file,
                    wait=True,
                    thread=thread,
                )
                return mess
            else:
                mess = await webhook.send(
                    content=newContent,
                    username=display_username,
                    avatar_url=avatar_url,
                    embeds=embed,
                    files=file,
                    wait=True,
                )
                return mess
        except Exception as e:
            await webhook.send(content=str(e))
            if thread != None:
                mess = await webhook.send(
                    content=newContent,
                    username="CaptainHook",
                    avatar_url=avatar_url,
                    embeds=embed,
                    files=file,
                    wait=True,
                    thread=thread,
                )
                return mess
            else:
                mess = await webhook.send(
                    content=newContent,
                    username="CaptainHook",
                    avatar_url=avatar_url,
                    embeds=embed,
                    files=file,
                    wait=True,
                )
                return mess

    @staticmethod
    async def postWebhookMessageProxy(channel, **kwargs) -> discord.WebhookMessage:
        """posts a message as a webhook
        :param message_content: content of message
        :param display_username: name to display of webhook
        :param avatar_url: url to paste webhook as.
        """
        text_channel = channel
        thread = None
        webhook, thread = await WebhookMessageWrapper.getWebhookInChannel(channel)
        mess = await WebhookMessageWrapper.postMessageWithWebhook(
            webhook, thread, **kwargs
        )
        return mess
