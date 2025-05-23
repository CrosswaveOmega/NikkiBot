import datetime
from typing import Union
import discord
from discord.ext import commands, tasks
from database import DatabaseSingleton
from cogs.dat_Starboard import (
    Starboard,
    StarboardEmojis,
    StarboardEntryTable,
    StarboardEntryGivers,
    StarboardIgnoreChannels,
)
from utility import (
    urltomessage,
)
import random
import asyncio


class StarboardCog(commands.Cog):
    """Based on the Star cog in RoboDanny."""

    def __init__(self, bot):
        self.bot = bot
        self.blacklist = ["im lost"]
        self.to_be_edited = {}
        self.lock = asyncio.Lock()
        self.emojilist = ["\N{HONEYBEE}", "<:2diverHeart:1221738356950564926>"]
        self.server_emoji_caches = {}
        self.ignore_channels_cache = {}

        self.timerloop.start()  # type: ignore

    def cog_unload(self):
        self.timerloop.cancel()  # type: ignore

    async def reaction_action(
        self, fmt: str, payload: discord.RawReactionActionEvent
    ) -> None:
        """Preform a starboard related action for reaction."""
        try:
            self.bot.logs.info(str(payload.emoji))
            if payload.guild_id not in self.server_emoji_caches:
                self.server_emoji_caches[
                    payload.guild_id
                ] = await StarboardEmojis.get_emojis(payload.guild_id, 100)

            if payload.guild_id not in self.ignore_channels_cache:
                self.ignore_channels_cache[
                    payload.guild_id
                ] = await StarboardIgnoreChannels.get_channels(payload.guild_id, 100)
            # ensure emoji is in cache
            if str(payload.emoji) not in self.server_emoji_caches[payload.guild_id]:
                return

            guild = self.bot.get_guild(payload.guild_id)  # type: ignore
            if guild is None:
                return

            channel = guild.get_channel_or_thread(payload.channel_id)
            if not isinstance(channel, (discord.Thread, discord.TextChannel)):
                return
            if isinstance(channel, discord.Thread):
                if (
                    int(channel.parent_id)
                    in self.ignore_channels_cache[payload.guild_id]
                ):
                    return

            if int(payload.channel_id) in self.ignore_channels_cache[payload.guild_id]:
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
            ) > datetime.timedelta(days=30):
                self.bot.logs.info("Too big.")
                return

            async with self.lock:
                message = await channel.fetch_message(payload.message_id)

                url = message.jump_url
                starrer = payload.member or (await guild.fetch_member(payload.user_id))
                if starrer is None or starrer.bot:
                    return

                if message.author.bot:
                    return

                if fmt == "star":
                    blacklist_words = self.blacklist
                    if any(word in message.content.lower() for word in blacklist_words):
                        self.bot.logs.info("blacklist detected")
                        return
                    self.bot.logs.info(
                        f"adding starrer message {message.id} {guild.id} {starrer.id}"
                    )
                    await StarboardEntryGivers.add_starrer(
                        message.id,
                        guild.id,
                        starrer.id,
                        str(payload.emoji),
                        message.jump_url,
                    )
                    await StarboardEntryTable.add_or_update_entry(
                        guild.id,
                        message.id,
                        message.channel.id,
                        message.author.id,
                        message_url=url,
                    )
                else:
                    async with DatabaseSingleton.get_async_session() as session:
                        entry = await StarboardEntryTable.get_entry(
                            guild.id, message.id, session=session
                        )
                        if not entry:
                            return
                        old_entry = await StarboardEntryGivers.get_starrer(
                            guild.id, message.id, starrer.id
                        )

                        self.bot.logs.info(
                            f"unstarring message {message.id} {guild.id} {starrer.id}"
                        )
                        if old_entry:
                            if old_entry.emoji == str(payload.emoji):
                                self.bot.logs.info("Same emoji...")
                                await session.delete(old_entry)
                                await session.commit()
                            else:
                                self.bot.logs.info("Different emoji...")
                    await StarboardEntryTable.add_or_update_entry(
                        guild.id,
                        message.id,
                        message.channel.id,
                        message.author.id,
                        url,
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

    async def edit_one_random(self):
        """Edit one random key/value pair in the to be edited dictionary."""
        (bot_message, message) = random.choice(list(self.to_be_edited.items()))
        self.bot.logs.info(f"found url {bot_message} for {str(message)}")
        self.to_be_edited.pop(bot_message)
        mess = await urltomessage(bot_message, self.bot)
        if mess:
            self.bot.logs.info("Editing random Starboard Emoji")
            entry = await StarboardEntryTable.get_with_url(bot_message)
            starboard = await Starboard.get_starboard(mess.guild.id)
            if entry and starboard:
                if entry.total < starboard.threshold:
                    self.bot.logs.info(
                        f"...entry deleted bc {entry.total} is less than {starboard.threshold}"
                    )
                    await StarboardEntryTable.delete_entry_by_bot_message_url(
                        bot_message
                    )
                    await mess.delete()
                else:
                    self.bot.logs.info("...entry edited")
                    content, embed = await self.get_emoji_message(message, entry)
                    await mess.edit(content=content, embed=embed)
            else:
                self.bot.logs.info("...entry edited")
                await StarboardEntryTable.delete_entry_by_bot_message_url(bot_message)
        else:
            mess = await urltomessage(bot_message, self.bot, partial=True)
            starboard = await Starboard.get_starboard(mess.guild.id)
            starboard_channel = self.bot.get_channel(starboard.channel_id)
            entry = await StarboardEntryTable.get_entry(message.guild.id, message.id)
            if entry and starboard and starboard_channel:
                if entry.total >= starboard.threshold:
                    self.bot.logs.info("...Resending Message")
                    content, embed = await self.get_emoji_message(message, entry)
                    bm = await starboard_channel.send(content, embed=embed)
                    entry = await StarboardEntryTable.add_or_update_bot_message(
                        message.guild.id, message.id, bm.id, bm.jump_url
                    )
                else:
                    self.bot.logs.info("Purging Message due to lack of stars")
                    await StarboardEntryTable.delete_entry_by_bot_message_url(
                        bot_message
                    )
            else:
                self.bot.logs.info("Purging Message due to lack of starboard")
                await StarboardEntryTable.delete_entry_by_bot_message_url(bot_message)

    @tasks.loop(seconds=15)
    async def timerloop(self):
        try:
            async with self.lock:
                if self.to_be_edited:
                    await self.edit_one_random()
        except Exception as e:
            await self.bot.send_error(e, "Task Error")

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

    @starboard.command()
    async def add_emoji(
        self, ctx, emoji: Union[str, discord.PartialEmoji, discord.Emoji]
    ):
        """Add an emoji to this server's starboard settings."""
        existing = await Starboard.get_starboard(ctx.guild.id)
        if not existing:
            await ctx.send("No starboard found for this server.")
        get = await StarboardEmojis.get_emoji(ctx.guild.id, emoji)
        if get:
            await ctx.send(f"Valid emoji {emoji} is alrady in starboard config.")
        updated = await StarboardEmojis.add_emoji(ctx.guild.id, emoji)
        if updated:
            self.server_emoji_caches[ctx.guild.id] = await StarboardEmojis.get_emojis(
                ctx.guild.id, 100
            )
            await ctx.send(f"Valid emoji {emoji} added to starboard config.")

    @starboard.command()
    async def add_server_emoji(self, ctx: commands.Context):
        """Add an emoji to this server's starboard settings."""
        existing = await Starboard.get_starboard(ctx.guild.id)
        upd = 0
        if not existing:
            await ctx.send("No starboard found for this server.")
        for emoji in ctx.guild.emojis:
            await ctx.send(f"{emoji} emoji {upd}")
            get = await StarboardEmojis.get_emoji(ctx.guild.id, str(emoji))
            if get:
                await ctx.send(f"{emoji} emoji {str(get)}")
                pass
            else:
                updated = await StarboardEmojis.add_emoji(ctx.guild.id, str(emoji))
                if updated:
                    upd += 1

        if upd:
            self.server_emoji_caches[ctx.guild.id] = await StarboardEmojis.get_emojis(
                ctx.guild.id, 100
            )
            await ctx.send(f"{upd} emoji added to starboard config.")
        else:
            await ctx.send(f"{upd} emoji added to starboard config.")

    @starboard.command()
    async def display_emoji_message(self, ctx):
        """Display a message with all joined emoji."""
        existing = await Starboard.get_starboard(ctx.guild.id)
        if not existing:
            await ctx.send("No starboard found for this server.")
        emoji_list = await StarboardEmojis.get_emojis(ctx.guild.id, 100)
        joined_emoji = " ".join(emoji_list)
        if joined_emoji:
            await ctx.send(f"Emojis in starboard config: {joined_emoji}")
        else:
            await ctx.send("No emojis found in starboard config.")

    @starboard.command()
    async def remove_emoji(
        self, ctx, emoji: Union[str, discord.PartialEmoji, discord.Emoji]
    ):
        """Remove an emoji to this server's starboard settings."""
        existing = await Starboard.get_starboard(ctx.guild.id)
        if not existing:
            await ctx.send("No starboard found for this server.")
        updated = await StarboardEmojis.remove_emoji(ctx.guild.id, emoji)
        if updated:
            self.server_emoji_caches[ctx.guild.id] = await StarboardEmojis.get_emojis(
                ctx.guild.id, 100
            )
            await ctx.send(f"Valid emoji {emoji} removed from starboard config.")
        else:
            await ctx.send(f"Emoji {emoji} is not being tracked.")

    @starboard.group()
    async def ignore_channel(self, ctx):
        """Manage ignored channels for the starboard."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid subcommand. Use add, remove, or list.")

    @ignore_channel.command()
    async def addchannel(self, ctx, channel: discord.TextChannel):
        """Ignore a channel from the starboard."""
        existing = await StarboardIgnoreChannels.get_channel(ctx.guild.id, channel.id)
        if existing:
            await ctx.send(f"{channel.mention} is already ignored.")
        else:
            await StarboardIgnoreChannels.add_channel(ctx.guild.id, channel.id)
            self.ignore_channels_cache.setdefault(ctx.guild.id, set()).add(channel.id)
            await ctx.send(f"Added {channel.mention} to ignored channels.")

    @ignore_channel.command()
    async def removechannel(self, ctx, channel: discord.TextChannel):
        """Remove a channel from the ignored list."""
        removed = await StarboardIgnoreChannels.remove_channel(ctx.guild.id, channel.id)
        if removed:
            self.ignore_channels_cache.get(ctx.guild.id, set()).discard(channel.id)
            await ctx.send(f"Removed {channel.mention} from ignored channels.")
        else:
            await ctx.send(f"{channel.mention} was not in the ignored list.")

    @ignore_channel.command()
    async def list(self, ctx):
        """List ignored channels."""
        ignored_channels = await StarboardIgnoreChannels.get_channels(ctx.guild.id)
        if ignored_channels:
            channel_mentions = [
                f"<#{channel.channel_id}>" for channel in ignored_channels
            ]
            await ctx.send("Ignored channels: " + ", ".join(channel_mentions))
        else:
            await ctx.send("No ignored channels.")

    @starboard.command()
    async def migrate(self, ctx):
        """Set the star threshold for the starboard."""
        existing = await Starboard.get_starboard(ctx.guild.id)
        if not existing:
            await ctx.send("Starboard does not exist for this server.")
            return
        async with DatabaseSingleton.get_async_session() as session:
            all_entries = await StarboardEntryTable.get_entries_by_guild(
                ctx.guild.id, session=session
            )
            for i, e in enumerate(all_entries):
                self.bot.logs.info("checking entry {i}")
                starrers = []
                message = await urltomessage(e.message_url, ctx.bot)
                if not message:
                    await session.delete(e)
                    continue
                for react in message.reactions:
                    if str(react.emoji) in self.server_emoji_caches[ctx.guild.id]:
                        async for user in react.users():
                            starrers.append(
                                (
                                    message.id,
                                    ctx.guild.id,
                                    user.id,
                                    str(react.emoji),
                                    e.message_url,
                                )
                            )
                if starrers:
                    await StarboardEntryGivers.add_starrers_bulk(
                        starrers, session=session
                    )

                e.total = await StarboardEntryGivers.count_starrers(
                    ctx.guild.id, message.id, session=session
                )

            await session.commit()
            await ctx.send("Done")

    @starboard.command()
    async def dump_stars(self, ctx):
        """Dump a list of all stars to the chat."""
        existing = await Starboard.get_starboard(ctx.guild.id)
        if not existing:
            await ctx.send("Starboard does not exist for this server.")
            return
        async with DatabaseSingleton.get_async_session() as session:
            all_entries = await StarboardEntryTable.get_entries_by_guild(
                ctx.guild.id, session=session
            )
            listv = ""
            for i, e in enumerate(all_entries):
                # await ctx.send(str(e))
                if e.bot_message_url is None:
                    await ctx.send(f"deleting {e}")
                    await session.delete(e)
                if len(listv) + len(f"{str(e)}\n") >= 1500:
                    await ctx.send(listv)
                    listv = ""
                listv += f"{i},{str(e)}\n"
            if listv:
                await ctx.send(listv)

            await session.commit()
            await ctx.send("Done")

    @starboard.command()
    async def audit_stars(self, ctx):
        """Dump a list of all stars to the chat."""
        existing = await Starboard.get_starboard(ctx.guild.id)
        if not existing:
            await ctx.send("Starboard does not exist for this server.")
            return
        async with DatabaseSingleton.get_async_session() as session:
            all_entries = await StarboardEntryTable.get_entries_by_guild(
                ctx.guild.id, session=session
            )
            alls = []
            for i, e in enumerate(all_entries):
                # await ctx.send(str(e))
                if e.bot_message_url is None:
                    alls.append(f"deleting: {i},{str(e)}\n")
                    await session.delete(e)
                else:
                    mess = await urltomessage(e.bot_message_url, self.bot)
                    if not mess:
                        await ctx.send(f"{str(e)} is not in starboard channel!")
                        alls.append(f"deleting: {i} ,{str(e)}\n")
                        await session.delete(e)

            await session.commit()
            await ctx.send(f"Audited and removed {len(alls)}")
            await ctx.send("Done")

    async def update_starboard_message(
        self, guild: discord.Guild, message: discord.Message, bot_message: str
    ) -> None:
        """
        Update the starboard message or add a new one based on entry threshold.

        Args:
            guild (discord.Guild): The guild where the message is located.
            message (discord.Message): The original message to be added or checked on starboard.
            bot_message (str): The URL of the bot's starboard message.
        """
        starboard = await Starboard.get_starboard(guild.id)
        if not starboard:
            return
        self.bot.logs.info(bot_message, message)
        starboard_channel = self.bot.get_channel(starboard.channel_id)
        entry = await StarboardEntryTable.get_entry(guild.id, message.id)
        if not bot_message:
            if entry.total >= starboard.threshold:
                content, embed = await self.get_emoji_message(message, entry)
                bm = await starboard_channel.send(content, embed=embed)
                entry = await StarboardEntryTable.add_or_update_bot_message(
                    guild.id, message.id, bm.id, bm.jump_url
                )
        else:
            self.to_be_edited[bot_message] = message

    async def get_emoji_message(
        self, message: discord.Message, stars: StarboardEntryTable
    ) -> tuple[str, discord.Embed]:
        """
        Generates a message with an emoji and returns it along with an embed based on the input message.

        Args:
            message (discord.Message): The original Discord message.
            stars (int): The number of emojis to display.

        Returns:
            tuple[str, discord.Embed]: The message content and the embed.
        """
        assert isinstance(message.channel, (discord.abc.GuildChannel, discord.Thread))
        emlist = await StarboardEntryGivers.list_starrer_emojis(
            stars.guild_id, stars.message_id
        )
        unique = []
        for e in emlist:
            if e not in unique:
                unique.append(e)
        emoji = ",".join(unique)

        if stars.total > 1:
            content = (
                f"{emoji} **{stars.total}** {message.channel.mention} ID: {message.id}"
            )
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
