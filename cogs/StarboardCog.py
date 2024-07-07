import datetime
import discord
from discord.ext import commands, tasks
from cogs.dat_Starboard import Starboard, StarboardEntryTable
from utility import (
    urltomessage,
)
import random
import asyncio


class StarboardCog(commands.Cog):
    """Based on the Star cog in RoboDanny."""

    def __init__(self, bot):
        self.bot = bot
        self.to_be_edited = set()
        self.lock = asyncio.Lock()

        self.timerloop.start()  # type: ignore

    def cog_unload(self):
        self.timerloop.cancel()  # type: ignore

    @tasks.loop(seconds=30)
    async def timerloop(self):
        async with self.lock:
            if self.to_be_edited:
                (bot_message, message) = random.choice(list(self.to_be_edited))
                self.to_be_edited.remove((bot_message,message))
                mess = await urltomessage(bot_message, self.bot)
                if mess:
                    entry = await StarboardEntryTable.get_entry(mess.guild.id, mess.id)
                    starboard = await Starboard.get_starboard(mess.guild.id)
                    if entry and starboard:
                        if entry.total < starboard.threshold:
                            await StarboardEntryTable.delete_entry_by_bot_message_url(
                                bot_message
                            )
                            await mess.delete()
                        else:
                            content, embed = self.get_emoji_message(
                                message, entry.total
                            )
                            await mess.edit(content=content, embed=embed)
                    else:
                        await StarboardEntryTable.delete_entry_by_bot_message_url(
                            bot_message
                        )
                else:
                    starboard = await Starboard.get_starboard(mess.guild.id)
                    starboard_channel = self.bot.get_channel(starboard.channel_id)
                    entry = await StarboardEntryTable.get_entry(
                        message.guild.id, message.id
                    )
                    if entry and starboard and starboard_channel:
                        if entry.total > starboard.threshold:
                            content, embed = self.get_emoji_message(
                                message, entry.total
                            )
                            bm = await starboard_channel.send(content, embed=embed)
                            entry = await StarboardEntryTable.add_or_update_bot_message(
                                message.guild.id, message.id, bm.id, bm.jump_url
                            )
                        else:
                            await StarboardEntryTable.delete_entry_by_bot_message_url(
                                bot_message
                            )
                    else:
                        await StarboardEntryTable.delete_entry_by_bot_message_url(
                            bot_message
                        )

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def starboard(self, ctx):
        """Starboard management commands."""
        await ctx.send("Available subcommands: add, remove, show, set_threshold")

    @starboard.command()
    async def add(self, ctx, channel: discord.TextChannel, threshold: int):
        """Add a starboard to the server."""
        existing = await Starboard.get_starboard(ctx.guild.id)
        if existing:
            await ctx.send("Starboard already exists for this server.")
            return

        await Starboard.add_starboard(ctx.guild.id, channel.id, threshold)
        await ctx.send(
            f"Starboard added to {channel.mention} with a threshold of {threshold} stars."
        )

    @starboard.command()
    async def remove(self, ctx):
        """Remove the starboard from the server."""
        removed = await Starboard.remove_starboard(ctx.guild.id)
        if removed:
            await ctx.send("Starboard removed.")
        else:
            await ctx.send("No starboard found for this server.")

    @starboard.command()
    async def show(self, ctx):
        """Show the current starboard settings."""
        existing = await Starboard.get_starboard(ctx.guild.id)
        if not existing:
            await ctx.send("No starboard found for this server.")
            return

        channel = self.bot.get_channel(existing.channel_id)
        await ctx.send(
            f"Starboard channel: {channel.mention}\nThreshold: {existing.threshold}"
        )

    @starboard.command()
    async def set_threshold(self, ctx, threshold: int):
        """Set the star threshold for the starboard."""
        updated = await Starboard.set_threshold(ctx.guild.id, threshold)
        if updated:
            await ctx.send(f"Starboard threshold set to {threshold} stars.")
        else:
            await ctx.send("No starboard found for this server.")

    async def reaction_action(
        self, fmt: str, payload: discord.RawReactionActionEvent
    ) -> None:
        try:
            if str(payload.emoji) != "\N{Honeybee}":
                return

            guild = self.bot.get_guild(payload.guild_id)  # type: ignore
            if guild is None:
                return

            channel = guild.get_channel_or_thread(payload.channel_id)
            if not isinstance(channel, (discord.Thread, discord.TextChannel)):
                return
            starboard = await Starboard.get_starboard(guild.id)
            if starboard:
                if starboard.channel_id == channel.id:
                    return
            else:
                return
            if (
                discord.utils.utcnow()
                - discord.utils.snowflake_time(payload.message_id)
            ) > datetime.timedelta(days=7):
                return
            async with self.lock:
                message = await channel.fetch_message(payload.message_id)

                url = message.jump_url
                starrer = payload.member
                if starrer:
                    if starrer.bot:
                        return
                if fmt == "star":

                    await StarboardEntryTable.add_or_update_entry(
                        guild.id,
                        message.id,
                        message.channel.id,
                        message.author.id,
                        message_url=url,
                    )
                else:
                    entry = await StarboardEntryTable.get_entry(guild.id, message.id)
                    if not entry:
                        return
                    await StarboardEntryTable.add_or_update_entry(
                        guild.id,
                        message.id,
                        message.channel.id,
                        message.author.id,
                        url,
                        -1,
                    )
                entry = await StarboardEntryTable.get_entry(guild.id, message.id)
                await self.update_starboard_message(
                    guild, message, entry.bot_message_url
                )
        except Exception as e:
            await self.bot.send_error(e, "React", True)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        if not isinstance(channel, discord.TextChannel):
            return

        starboard = await Starboard.get_starboard(channel.guild.id)
        if starboard.channel_id != channel.id:
            return

        # The starboard channel got deleted, so let's clear it from the database.
        await Starboard.remove_starboard(channel.guild.id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        await self.reaction_action("star", payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        await self.reaction_action("unstar", payload)

    @commands.Cog.listener()
    async def on_raw_reaction_clear(
        self, payload: discord.RawReactionClearEmojiEvent
    ) -> None:
        guild = self.bot.get_guild(payload.guild_id)  # type: ignore
        if guild is None:
            return

        channel = guild.get_channel_or_thread(payload.channel_id)
        if channel is None or not isinstance(
            channel, (discord.Thread, discord.TextChannel)
        ):
            return

        entry = await StarboardEntryTable.get_entry(guild.id, payload.message_id)
        if entry.bot_message_url is None:
            return

        starboard = await Starboard.get_starboard(channel.guild.id)
        if starboard.channel_id is None:
            return
        urlv = entry.bot_message_url

        await StarboardEntryTable.delete_entry_by_bot_message_url(urlv)
        msg = await urltomessage(urlv, self.bot)
        if msg is not None:
            await msg.delete()

    async def update_starboard_message(self, guild, message, bot_message):
        starboard = await Starboard.get_starboard(guild.id)
        print(starboard)
        if not starboard:
            return

        starboard_channel = self.bot.get_channel(starboard.channel_id)
        entry = await StarboardEntryTable.get_entry(guild.id, message.id)
        if not bot_message:
            if entry.total>=starboard.threshold:
                content, embed = self.get_emoji_message(message, entry.total)
                bm = await starboard_channel.send(content, embed=embed)
                entry = await StarboardEntryTable.add_or_update_bot_message(
                    guild.id, message.id, bm.id, bm.jump_url
                )
        else:
            self.to_be_edited.add((bot_message, message))

    def get_emoji_message(
        self, message: discord.Message, stars: int
    ) -> tuple[str, discord.Embed]:
        """
        Generates a message with an emoji and returns it along with an embed based on the input message.

        Args:
            message (discord.Message): The original Discord message.
            stars (int): The number of stars to display.

        Returns:
            tuple[str, discord.Embed]: The message content and the embed.
        """
        assert isinstance(message.channel, (discord.abc.GuildChannel, discord.Thread))
        emoji = "\N{Honeybee}"

        if stars > 1:
            content = f"{emoji} **{stars}** {message.channel.mention} ID: {message.id}"
        else:
            content = f"{emoji} {message.channel.mention} ID: {message.id}"

        embed = discord.Embed(description=message.content)
        if message.embeds:
            data = message.embeds[0]
            if data.type == "image" and data.url:
                embed.set_image(url=data.url)

        if message.attachments:
            file = message.attachments[0]
            spoiler = file.is_spoiler()
            if not spoiler and file.filename.lower().endswith(
                ("png", "jpeg", "jpg", "gif", "webp")
            ):
                embed.set_image(url=file.url)
            elif spoiler:
                embed.add_field(
                    name="Attachment",
                    value=f"||[{file.filename}]({file.url})||",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Attachment",
                    value=f"[{file.filename}]({file.url})",
                    inline=False,
                )

        ref = message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            embed.add_field(
                name="Replying to...",
                value=f"[{ref.resolved.author}]({ref.resolved.jump_url})",
                inline=False,
            )

        embed.add_field(
            name="Original", value=f"[Jump!]({message.jump_url})", inline=False
        )
        embed.set_author(
            name=message.author.display_name, icon_url=message.author.display_avatar.url
        )
        embed.timestamp = message.created_at
        embed.color = 0xE9AB17
        return content, embed


async def setup(bot):
    await bot.add_cog(StarboardCog(bot))
