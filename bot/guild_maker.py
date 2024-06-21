import configparser
import discord
import aiohttp
from assetloader import AssetLookup
import gui

"""
To make it even easier, this script is for creating a local home guild for newly initalized bots.

"""


async def create_guild(bot, guild_name, guild_icon):
    """
    Creates a new guild with the specified name and icon
    """
    async with aiohttp.ClientSession() as session:
        icon_data = await session.get(guild_icon)
        icon_bytes = await icon_data.read()

    guild = await bot.create_guild(name=guild_name, icon=icon_bytes)
    return guild


async def new_guild(bot):
    """
    Creates a new guild with the specified name, icon, channels, roles, and invites
    """
    guild_name = f"{bot.user.name}'s Home Guild"  # Replace with the desired guild name
    guild_icon_url = (
        bot.application.icon.url
    )  # Replace with the URL of the desired guild icon

    # Create the new guild with the specified name and icon
    guild = await create_guild(bot, guild_name, guild_icon_url)
    error_channel_id = 0
    # Create the seven channels and one voice channel
    channels = [
        "updates",
        "resources",
        "internal_debug",
        "error_log",
        "general",
        "off-topic",
        "voicechannel",
    ]
    voice_channel = "voicechannel"
    for channel in channels:
        if channel == voice_channel:
            await guild.create_voice_channel(channel)
        else:
            ch = await guild.create_text_channel(channel)
            if channel == "error_log":
                error_channel_id = ch.id

    # Create the admin role and give it administrator permissions
    admin_role = await guild.create_role(
        name="admin", permissions=discord.Permissions(administrator=True)
    )

    # Generate an invite to the guild and send it in a message
    invite = await guild.text_channels[0].create_invite()
    user = await bot.fetch_user(bot.application.owner.id)

    await user.send(
        f'Hello world!  I\'ve created a new guild "{guild.name}" with an invite: {invite.url}'
    )
    config = configparser.ConfigParser()
    config.read("config.ini")
    config["vital"] = {"cipher": config.get("vital", "cipher")}
    config["optional"] = {"error_channel_id": error_channel_id}
    AssetLookup.set_asset("homeguild", guild.id, "main")
    AssetLookup.save_assets()
    gui.gprint(f"Error_channel={error_channel_id}")
    config.write(open("config.ini", "w"))

    # Give the admin role to the bot owner when they join the server
    @bot.event
    async def on_member_join(member):
        if member.id == bot.application.owner.id:
            await member.add_roles(admin_role)
