from typing import Optional, Tuple, Union
import discord
import gui


class LinkError(Exception):
    pass


class BotError(Exception):
    pass


def urlto_gcm_ids(link="") -> Tuple[int, int, int]:
    """extract guildid, channelid, and messageid from a link.

    Args:
        link (str, optional): _description_. Defaults to "".

    Raises:
        LinkError: If the passed in link is either not a string or does not contain the needed ids.

    Returns:
        guild_id, channel_id, message_id
    """
    # Attempt to extract guild, channel, and messageids from url.
    if not isinstance(link, str):
        raise LinkError(f"Link {link} is not a string.")
    linkcontents = link.split("/")
    if len(linkcontents) < 7:
        raise LinkError(f"Link {link} only has {len(linkcontents)} is not valid.")
    guild_id = linkcontents[4]
    channel_id = linkcontents[5]
    message_id = linkcontents[6]
    return guild_id, channel_id, message_id


async def urltomessage(
    link="", bot=None, partial=False
) -> Optional[Union[discord.Message, discord.PartialMessage]]:
    """return a discord message from a message url."""
    message = None
    try:
        guild = channel = message = None
        if bot is None:
            raise BotError("Bot was not defined.")
        tup = urlto_gcm_ids(link)
        guild_id, channel_id, message_id = tup
        if guild_id != "@me":
            guild = bot.get_guild(int(guild_id))
            if guild is None:
                raise BotError(f"Failed to get guild {guild_id}.")
            channel = guild.get_channel_or_thread(int(channel_id))
        else:
            bot.get_channel(int(channel_id))
        if channel is None:
            raise BotError("Failed to get channel {channel_id}.")
        message = None
        try:
            if partial:
                message = channel.get_partial_message(int(message_id))
            else:
                message = await channel.fetch_message(int(message_id))
        except discord.errors.NotFound:
            raise BotError(
                f"Failed to get message {message_id} from {link}."
            )
    except Exception as e:
        gui.gprint(e)
        if bot:
            await bot.send_error(e, "URL_TO_MESSAGE_ERROR")
        return None
    return message
