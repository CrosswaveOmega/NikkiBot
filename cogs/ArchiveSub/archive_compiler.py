import asyncio

# import datetime
from datetime import datetime
from typing import List, Optional, Tuple

import discord
from discord.ext import commands

import gui
from bot import (
    StatusEditMessage,
)
from database import ServerArchiveProfile
from utility import WebhookMessageWrapper as web
from utility import (
    seconds_to_time_string,
    urltomessage,
)
from utility.debug import Timer

from .archive_database import ArchivedRPMessage, ChannelSep

from .historycollect import check_channel, collect_server_history
from .collect_group_index import do_group

from .archive_message_templates import ArchiveMessageTemplate as MessageTemplates


class ArchiveProgress:
    __slots__ = (
        "message_total",
        "group_total",
        "m_arc",
        "g_arc",
        "avgtime",
        "avgsep",
        "t_mess",
        "t_sep",
    )

    def __init__(self, message_total, group_total, m_arc=0, g_arc=0, profile=None):
        self.message_total = message_total
        self.group_total = group_total
        self.m_arc = m_arc
        self.g_arc = g_arc
        self.avgtime = 2.5
        self.avgsep = 3
        self.t_mess = 0
        self.t_sep = 0
        if profile:
            avgtime = profile.average_message_archive_time
            if not avgtime:
                avgtime = 2.5
            avgsep = profile.average_sep_archive_time
            if not avgsep:
                avgsep = 3
            self.avgtime = avgtime
            self.avgsep = avgsep

    def get_avgs(self):
        savg = self.t_sep / max(self.g_arc, 1)
        mavg = self.t_mess / max(self.m_arc, 1)
        return savg, mavg

    def remain_time(self):
        return ((self.message_total - self.m_arc) * self.avgtime) + (
            (self.group_total - self.g_arc) * self.avgsep
        )

    def get_string(self, index=0, ml=0):
        total = f"Currently on group {self.g_arc}/{self.group_total}.\n"
        if index != 0 and ml != 0:
            total += f"Current group has {int(ml - index)} messages left\n"
        total += f"Currently archived {self.m_arc} messages out of {self.message_total} total.\n"
        total += f"This is going to take another... {seconds_to_time_string(int(self.remain_time()))}"
        return total

    def get_remaining(self):
        se = f"{self.group_total - self.g_arc} groups,"
        se += f" {self.message_total - self.m_arc} messages left."
        se += (
            f"\n estimated {seconds_to_time_string(int(self.remain_time()))} remaining."
        )
        return se

    def merge(self, other):
        """return a new archiveprogress object,"""
        s = ArchiveProgress(
            self.message_total,
            self.group_total,
            self.m_arc + other.m_arc,
            self.g_arc + other.g_arc,
        )
        s.avgtime = self.avgtime
        s.avgsep = self.avgsep
        return s


class ArchiveCompiler:
    def __init__(self, ctx, lazymode=False, send_all_clear_message=True):
        self.ctx = ctx
        self.lazy = lazymode
        self.bot = ctx.bot
        self.auth = ctx.message.author
        self.channel = ctx.message.channel
        self.guild = self.channel.guild
        self.send_all_clear_message = send_all_clear_message

        self.update = True
        self.archive_from = "server"
        self.dynamicwait = False
        self.timebetweenmess = 2.0
        self.characterdelay = 0.05
        self.inital_edit_mess = None

        self.ap = ArchiveProgress(0, 0)
        self.sep_total = 0

        self.timeoff = None

        self.avgtime = 2.0
        self.t_mess = self.t_sep = 0
        self.avgsep = 3.0
        self.supertup = (None, None, None)

    def format_embed(self, index=1, ml=1):
        total = "<a:LetWalkR:1118191001731874856>" + self.ap.get_string(index, ml)
        if self.timeoff:
            res = self.timeoff.merge(self.ap)
            total += "\n" + res.get_remaining()

        embed = discord.Embed(description=total)
        return embed

    async def setup(self):
        ctx = self.ctx
        if self.guild == None:
            await self.ctx.send("This command will only work inside a guild.")
            return False
        profile = ServerArchiveProfile.get_or_new(self.guild.id)

        if profile.history_channel_id == 0:
            await MessageTemplates.get_server_archive_embed(
                self.ctx, "Set a history channel first."
            )
            return False
        archive_channel = self.guild.get_channel(profile.history_channel_id)
        if archive_channel == None:
            await MessageTemplates.get_server_archive_embed(
                self.ctx, "I can't seem to access the history channel, it's gone!"
            )
            return False

        passok, statusmessage = check_channel(archive_channel)

        if not passok:
            await MessageTemplates.server_archive_message(self.ctx, statusmessage)
            return False

        m = await ctx.channel.send("Initial check OK!")
        if profile.last_archive_time == None:
            if ctx.author.id == ctx.bot.user.id and self.lazy == False:
                await ctx.send(
                    "This is my first time archiving this server, please start the first archive manually."
                )
                return False
            else:
                await ctx.send(
                    "## Hold up!  This is my first time archiving this server!\n"
                    + "If your server has over 10,000 messages, you should use a lazy compile first!"
                )
                confirm, mes = await MessageTemplates.confirm(
                    ctx,
                    "Do you have less than 10,000 messages?",
                    ephemeral=False,
                )

                if not confirm:
                    await ctx.send(
                        "**Please call the `>lazymode` command for your first archive.**"
                    )
                    return False
        self.bot.add_act(str(ctx.guild.id) + "arch", "archiving server...")
        self.supertup = (m, profile, archive_channel)
        return True

    async def collect(self, m, profile: ServerArchiveProfile):
        await m.edit(content="Collecting server history...")

        totalcharlen = 0
        new_last_time = 0
        if self.archive_from == "server":
            messages3, totalcharlen, new_last_time = await collect_server_history(
                self.ctx, update=self.update
            )

    async def group(self, m, profile: ServerArchiveProfile):
        await m.edit(content="Grouping into separators, this may take a while.")

        lastgroup = profile.last_group_num
        ts, group_id = await do_group(
            self.guild.id, profile.last_group_num, ctx=self.ctx
        )

        fullcount = ts
        profile.update(last_group_num=group_id)

        gui.gprint(lastgroup, group_id)

        gui.gprint("next")
        avgtime = profile.average_message_archive_time
        if not avgtime:
            avgtime = 2.5
        avgsep = profile.average_sep_archive_time
        if not avgsep:
            avgsep = 3
        self.avgtime = avgtime
        self.avgsep = avgsep
        ap = ArchiveProgress(fullcount, group_id, 0, 0)
        total_time_for_cluster = ap.remain_time()
        timestring = seconds_to_time_string(int(total_time_for_cluster))
        return fullcount, group_id, timestring

    async def edit_embed_and_neighbors(self, target: ChannelSep):
        """
        This code checks if the target ChannelSep object has a
        posted_url attribute, and then edits it's neighbors.

        """

        async def edit_if_needed(target):
            if target:
                message = await urltomessage(target.posted_url, self.bot)

                emb, lc = target.create_embed()
                gui.gprint(lc)
                target.update(neighbor_count=lc)
                await message.edit(embeds=[emb])

        gui.gprint(target, target.posted_url)
        if target.posted_url:
            iL = target.get_neighbor(False, False, False)
            cL = target.get_neighbor(True, False, False)
            gui.gprint(iL, cL, target)

            await edit_if_needed(iL)
            await edit_if_needed(cL)
            gui.gprint("New posted_url value for ChannelSep")

    def get_current_time(self):
        pass

    async def post_setup(
        self,
        m: discord.Message,
        profile: ServerArchiveProfile,
        archive_channel: discord.TextChannel,
        upper_lim: Optional[int] = None,
    ) -> Tuple[StatusEditMessage, List[ChannelSep]]:
        """
        Get grouped list, create the staus message, and estimate the remaining time.
        """

        avgtime = profile.average_message_archive_time
        gt = mt = 0
        needed = ChannelSep.get_posted_but_incomplete(self.guild.id)
        if upper_lim:
            grouped = []
            mt = sum(len(sep.get_messages()) for sep in grouped)
            gt = len(grouped)
            ap = ArchiveProgress(mt, gt, profile=profile)
            off = 0

            while ap.remain_time() < upper_lim:
                this_grouped = ChannelSep.get_unposted_separators(self.guild.id, 1, off)
                if not this_grouped:
                    break
                mt += sum(len(sep.get_messages()) for sep in this_grouped)
                gt += len(this_grouped)
                ap.message_total = mt
                ap.group_total = gt
                off += 1
                grouped.extend(this_grouped)

        else:
            grouped = ChannelSep.get_unposted_separators(self.guild.id)
        if needed:
            newgroup = []
            newgroup.extend(needed)
            newgroup.extend(grouped)
            grouped = newgroup

        gui.gprint(grouped, needed)

        message_total = sum(len(sep.get_messages()) for sep in grouped)
        sep_total = len(grouped)
        self.ap = ArchiveProgress(message_total, sep_total, profile=profile)

        outstring = f"It will take {seconds_to_time_string(int(self.ap.remain_time()))} to post in the archive channel."
        if int(self.ap.remain_time()) <= 0.1:
            outstring = "The Archive Channel is already up to date!"

        # Start posting

        await m.edit(content=outstring)
        embed = self.format_embed(0, 1)
        me = await self.ctx.channel.send(embed=embed)
        mt = StatusEditMessage(me, self.ctx)
        return mt, grouped

    async def post_sep(self, sep: ChannelSep, archive_channel):
        """Post or edit a Channel Separator Message."""
        if not sep.posted_url:
            emb, _ = sep.create_embed()
            chansep = await archive_channel.send(embed=emb)
            sep.update(posted_url=chansep.jump_url)
            await self.edit_embed_and_neighbors(sep)

            self.bot.database.commit()

        elif sep.posted_url and not sep.all_ok:
            old_message = await urltomessage(sep.posted_url, self.bot)
            emb, _ = sep.create_embed(cfrom=sep.posted_url)
            new_message = await archive_channel.send(embed=emb)
            jump_url = new_message.jump_url
            embedit, _ = sep.create_embed(cto=jump_url)
            await old_message.edit(embed=embedit)

    async def post_mess(self, index, amess, archive_channel):
        c, au, av = amess.content, amess.author, amess.avatar
        self.ap.m_arc += 1
        files = []
        for attach in amess.list_files():
            this_file = attach.to_file()
            files.append(this_file)
        pager = commands.Paginator(prefix="", suffix="")

        if len(c) > 2000:
            for l in c.split("\n"):
                pager.add_line(l)
            for page in pager.pages:
                webhookmessagesent = await web.postWebhookMessageProxy(
                    archive_channel,
                    message_content=page,
                    display_username=au,
                    avatar_url=av,
                    embed=amess.get_embed(),
                    file=files,
                )
            if webhookmessagesent:
                amess.update(posted_url=webhookmessagesent.jump_url)
        else:
            webhookmessagesent = await web.postWebhookMessageProxy(
                archive_channel,
                message_content=c,
                display_username=au,
                avatar_url=av,
                embed=amess.get_embed(),
                file=files,
            )
            if webhookmessagesent:
                amess.update(posted_url=webhookmessagesent.jump_url)
        await asyncio.sleep(self.timebetweenmess)

    async def post_groups(
        self,
        mt,
        grouped: List[ChannelSep],
        profile: ServerArchiveProfile,
        archive_channel: discord.TextChannel,
    ):
        """Iterate through groups and post the channel seps and archived messages to the Archive_channel

        Args:
            mt (StatusEditMessage): Status edit message
            grouped (List[ChannelSep]): List of grouped Channel Seps, retrieved through post_setup
            profile (ServerArchiveProfile): Profile of Server being archived
            archive_channel (discord.TextChannel): Archive Channel of server.
        """

        gui.gprint(archive_channel.name)

        for e, sep in enumerate(grouped):
            # Start posting
            self.ap.g_arc += 1
            gui.gprint(e, sep)
            gui.dprint(self.ap.remain_time())
            # POST SEPARATORS
            with Timer() as sep_timer:
                await self.post_sep(sep, archive_channel)
            pre_time = sep_timer.get_time()
            gui.gprint("sep_timer_time", pre_time)
            messages = sep.get_messages()
            m_len = len(messages)
            # Post every message in sep
            for index, amess in enumerate(messages):
                with Timer() as posttimer:
                    await self.post_mess(index, amess, archive_channel)

                embed = self.format_embed(index, m_len)
                await mt.editw(min_seconds=45, embed=embed)
                self.ap.t_mess += posttimer.get_time()
            # MARK SEP AS CONCLUDED.
            sep.update(all_ok=True)
            self.bot.database.commit()
            with Timer() as finishtime:
                await asyncio.sleep(2)
                embed = self.format_embed(m_len, m_len)
                await mt.editw(
                    min_seconds=30,
                    embed=embed,
                )
                self.bot.add_act(
                    str(self.guild.id) + "arch",
                    f"Currently on {e + 1}/{self.sep_total}.\n  This is going to take about...{seconds_to_time_string(int(self.ap.remain_time()))}",
                )
            posttime = finishtime.get_time()
            self.ap.t_sep += pre_time + posttime

    # done
    async def post(
        self,
        m,
        profile: ServerArchiveProfile,
        archive_channel: discord.TextChannel,
        upper_lim: Optional[int] = None,
    ):
        mt, grouped = await self.post_setup(
            m, profile, archive_channel, upper_lim=upper_lim
        )
        didthing = False
        if len(grouped) > 0:
            await self.post_groups(mt, grouped, profile, archive_channel)
            await asyncio.sleep(2)
            didthing = True
        await mt.delete()
        return didthing

    async def cleanup(self, profile: ServerArchiveProfile, m: discord.Message):
        game = discord.Game("{}".format("clear"))
        await self.bot.change_presence(activity=game)

        self.bot.remove_act(str(self.guild.id) + "arch")
        channel = await self.bot.fetch_channel(self.channel.id)
        latest = ArchivedRPMessage.get_latest_archived_rp_message(self.guild.id)

        profile.update(last_archive_time=latest.created_at)
        self.ap.get_avgs()
        if self.ap.g_arc > 0 and self.ap.m_arc > 0:
            septime, mestime = self.ap.get_avgs()
            profile.update(
                average_sep_archive_time=septime, average_message_archive_time=mestime
            )
        self.bot.database.commit()
        if self.send_all_clear_message:
            await MessageTemplates.server_archive_message(
                channel,
                f"Archive operation completed at <t:{int(datetime.now().timestamp())}:f>",
            )
        else:
            embed = MessageTemplates.get_server_archive_embed_simple(
                channel.guild,
                f"Archive operation completed at <t:{int(datetime.now().timestamp())}:f>",
            )
            await m.edit(content=f"{m.content}", embed=embed)

    async def start(self):
        outcome = await self.setup()
        if not outcome:
            return False
        m, profile, archive_channel = self.supertup
        await self.collect(m, profile)
        await self.group(m, profile)
        await self.post(m, profile, archive_channel)
        await self.cleanup(profile, m)
        return profile
