import asyncio
from typing import List
import gui
from datetime import datetime, timedelta, timezone
from .archive_database import ArchivedRPMessage, ChannelSep, HistoryMakers
from database import DatabaseSingleton
from queue import Queue
from bot import StatusEditMessage
from utility import (
    seconds_to_time_string,
    urltomessage,
)

"""

Groups the collected history messages into "ChannelSep" objects, that store the location and time of each set of 
server message.

"""
DEBUG_MODE = False


async def iterate_backlog(backlog: List[ArchivedRPMessage], group_id: int, count=0):
    # Goes through queue once.
    tosend = []
    now = datetime.now()
    initial = len(backlog)
    archived = 0

    buckets = {}  # Dictionary to hold buckets of messages
    finished_buckets = []  # Dictionary to hold finished buckets
    optotal = 0
    opcount = 0
    chars = {}
    for hm in backlog:
        time = datetime.now()
        if DEBUG_MODE:
            gui.dprint(f"Backlog Pass {group_id}:")

        if (datetime.now() - now).total_seconds() > 1:
            gui.dprint(
                f"Backlog Pass {group_id}: {archived} out of {initial} messages, with {count} remaining."
            )
            # await asyncio.sleep(0.02)
            now = datetime.now()

        # hm: ArchivedRPMessage = backlog.get()
        channelind = hm.get_chan_sep()

        # Find the bucket for the current channel separator
        bucket = buckets.get(channelind)

        if bucket:
            # Check if the author is in any bucket
            if chars.get(hm.author, None):
                # This author is in a bucket.  Make sure it's not this one.
                if chars[hm.author]["ci"] != channelind:
                    # It's not this bucket.  Check if this bucket is newer, if it isn't
                    # Then time to split.
                    if chars[hm.author]["gid"] > bucket["group_id"]:
                        # The bucket the author is inside is NEWER than
                        # the current bucket.  Time to fix that.
                        finished_buckets.append(buckets[channelind])
                        group_id += 1
                        bucket = {"messages": 0, "authors": 0, "group_id": group_id}
                        buckets[channelind] = bucket

                        hm.update(channel_sep_id=buckets[channelind]["group_id"])
                        HistoryMakers.add_channel_sep_if_needed(
                            hm, buckets[channelind]["group_id"]
                        )
                        gui.dprint(
                            f"Backlog Pass {group_id}: {archived} out of {initial} messages, making a new bucket for {channelind}"
                        )
                    else:
                        gui.dprint(
                            f"Backlog Pass {group_id}: Author is in older bucket, it's ok to overwrite."
                        )

        # If the bucket doesn't exist, create a new one
        if not bucket:
            group_id += 1
            gui.dprint(
                f"Backlog Pass {group_id}: {archived} out of {initial} messages, making a new bucket for {channelind}"
            )
            bucket = {"messages": 0, "authors": 0, "group_id": group_id}
            buckets[channelind] = bucket

            hm.update(channel_sep_id=buckets[channelind]["group_id"])
            HistoryMakers.add_channel_sep_if_needed(hm, buckets[channelind]["group_id"])

        # Update the channel separator ID of the message
        hm.update(channel_sep_id=buckets[channelind]["group_id"])
        archived += 1
        chars[hm.author] = {"ci": channelind, "gid": buckets[channelind]["group_id"]}
        # Add the message to the bucket
        bucket["messages"] += 1
        # bucket['authors'].add(hm.author)
        res = datetime.now() - time
        optotal += res.total_seconds()
        await asyncio.sleep(float(0.002))
    gui.dprint(
        "PASS TOOK ",
        seconds_to_time_string(optotal),
        "with ",
        archived,
        "messages.  avg",
        optotal / max(1, archived),
    )
    if DEBUG_MODE:
        gui.dprint("Pass complete.")

    DatabaseSingleton("voc").commit()
    return tosend, group_id


async def iterate_backlog_old(backlog: Queue, group_id: int, count=0):
    tosend = []
    now = datetime.now()
    inital = backlog.qsize()
    archived = 0
    while backlog.empty() == False:
        if DEBUG_MODE:
            gui.dprint(f"Backlog Pass {group_id}:")
        new_backlog = Queue()
        charsinotherbacklog = set()
        current_chana = None
        running = True
        if (datetime.now() - now).total_seconds() > 1:
            await asyncio.sleep(0.1)
            now = datetime.now()
        while backlog.empty() == False:
            if (datetime.now() - now).total_seconds() > 1:
                gui.dprint(
                    f"Backlog Pass {group_id}: {archived} out of {inital} messages, with {count} remaining."
                )
                await asyncio.sleep(0.1)
                now = datetime.now()
            hm = backlog.get()
            channelind = hm.get_chan_sep()
            if hm.author in charsinotherbacklog and hm.get_chan_sep() == current_chana:
                running = False
                current_chana = "CHARA_DID_A_SPLIT"
            if current_chana is None:
                group_id += 1
                if DEBUG_MODE:
                    gui.dprint("inb", current_chana, hm.get_chan_sep(), group_id)
                current_chana = channelind
            if channelind == current_chana and running:
                if DEBUG_MODE:
                    gui.dprint("in", current_chana, hm.get_chan_sep(), group_id)
                hm.update(channel_sep_id=group_id)
                archived += 1
                HistoryMakers.add_channel_sep_if_needed(hm, group_id)
            else:
                new_backlog.put(hm)
                charsinotherbacklog.add(hm.author)
        if DEBUG_MODE:
            gui.dprint("Pass complete.")
        DatabaseSingleton("voc").commit()
        backlog = new_backlog
    return tosend, group_id


async def do_group_old(
    server_id,
    group_id=0,
    forceinterval=240,
    withbacklog=240,
    maximumwithother=200,
    ctx=None,
    glimit=999999999,
    upperlim=None,
):
    """Groups the collected history messages into 'ChannelSep' objects

    Args:
        server_id (str): ID of the server
        group_id (int, optional): ID of the group. Defaults to 0.
        forceinterval (int, optional): Forced interval time in minutes. Defaults to 240.
        withbacklog (int, optional): Time frame for backlog messages in minutes. Defaults to 240.
        maximumwithother (int, optional): Maximum count of messages that can be grouped with others. Defaults to 200.
        ctx (Context, optional): Context passed for operations like sending messages. Defaults to None.
        glimit (int, optional): Group limit count which decides when to split groups. Defaults to 999999999.
        upperlim (_type_, optional): Upper limit to decide group boundaries. Defaults to None.

    Returns:
        tuple: Number of messages grouped and last used group ID.
    """
    gui.dprint("Starting run.")

    count = ArchivedRPMessage().count_messages_without_group(server_id)
    new_list, new_count = [], 0
    stopcount = 0
    countlim = 2**64
    status_mess = (
        StatusEditMessage(
            await ctx.channel.send(
                f"<a:LetWalkR:1118191001731874856> Grouping: total of {count} messages."
            ),
            ctx,
        )
        if ctx
        else None
    )
    firsttime, now = (
        datetime.fromtimestamp(0).replace(tzinfo=timezone.utc),
        datetime.now(),
    )

    while new_count < count:
        get_msg_result = ArchivedRPMessage().get_messages_without_group_batch(
            server_id, upperlim, new_count, 250
        )
        new_list.extend(get_msg_result[0])
        new_count = get_msg_result[1]
        stopcount += 1
        if stopcount > countlim:
            raise RecursionError("something has gone horribly wrong.")
        gui.dprint(f"Now at: {new_count}/{count}.")
        await asyncio.sleep(0.1)
        if status_mess:
            await status_mess.editw(
                min_seconds=2,
                content=f"<a:LetWalkR:1118191001731874856> Now at: {new_count}/{count}.<a:LetWalkR:1118191001731874856> ",
            )

    length, old_group_id = count, group_id
    to_send, current_chana, backlog, chars_in_backlog = [], None, Queue(), set()

    for i, hm in enumerate(new_list):
        if (datetime.now() - now).total_seconds() > 1:
            gui.dprint(f"Now at: {i}/{length}, group_id:{group_id}.")
            await asyncio.sleep(0.1)
            now = datetime.now()

        if status_mess:
            gui.dprint(f"Now at: {i}/{length}, group_id:{group_id}.")
            await status_mess.editw(
                min_seconds=10,
                content=f"<a:LetWalkR:1118191001731874856> Now at: {i}/{count}, group_id:{group_id}.<a:LetWalkR:1118191001731874856> ",
            )

        if DEBUG_MODE:
            gui.dprint("i", hm)

        my_time = (hm.created_at).replace(tzinfo=timezone.utc)
        chanin = hm.get_chan_sep()
        hm.is_active = False

        time_del = my_time - firsttime
        minutes = time_del.total_seconds() // 60

        splita = cc_count > maximumwithother and current_chana != chanin
        splitb = minutes >= withbacklog and (chanin != current_chana)
        splitc = minutes >= forceinterval

        # start a new group if split condition is met
        if splita or splitb or splitc:
            DatabaseSingleton("voc").commit()

            ts, group_id = await iterate_backlog(backlog, group_id, length - i)
            await asyncio.sleep(0.1)
            to_send += ts
            backlog, chars_in_backlog = Queue(), set()
            cc_count, current_chana = 0, None
            firsttime = my_time - (
                my_time - datetime.min.replace(tzinfo=timezone.utc)
            ) % timedelta(minutes=15)

        if current_chana is None:
            current_chana = hm.get_chan_sep()

            if (group_id - old_group_id) > glimit:
                DatabaseSingleton("voc").commit()
                ts, group_id = await iterate_backlog(backlog, group_id, length)
                to_send += ts
                gui.dprint("done")
                return to_send, group_id

            if DEBUG_MODE:
                gui.dprint("inb", current_chana, hm.get_chan_sep(), group_id)

        if chanin == current_chana:
            if DEBUG_MODE:
                gui.dprint("in", current_chana, hm.get_chan_sep(), group_id)
            backlog.put(hm)
            cc_count += 1
        else:
            backlog.put(hm)
            chars_in_backlog.add(hm.author)

    DatabaseSingleton("voc").commit()

    ts, group_id = await iterate_backlog(backlog, group_id, length)
    if status_mess:
        await status_mess.delete()

    to_send += ts

    return length, group_id


async def do_group(
    server_id,
    group_id=0,
    forceinterval=720,
    withbacklog=240,
    maximumwithother=200,
    ctx=None,
    glimit=999999999,
    upperlim=None,
):
    """Groups the collected history messages into 'ChannelSep' objects

    Args:
        server_id (str): ID of the server
        group_id (int, optional): ID of the group. Defaults to 0.
        forceinterval (int, optional): Forced interval time in minutes. Defaults to 240.
        withbacklog (int, optional): Time frame for backlog messages in minutes. Defaults to 240.
        maximumwithother (int, optional): Maximum count of messages that can be grouped with others. Defaults to 200.
        ctx (Context, optional): Context passed for operations like sending messages. Defaults to None.
        glimit (int, optional): Group limit count which decides when to split groups. Defaults to 999999999.
        upperlim (_type_, optional): Upper limit to decide group boundaries. Defaults to None.

    Returns:
        tuple: Number of messages grouped and last used group ID.
    """
    gui.dprint("Starting run.")

    count = ArchivedRPMessage().count_messages_without_group(server_id)
    new_list, new_count = [], 0

    status_mess = (
        StatusEditMessage(
            await ctx.channel.send(
                f"<a:LetWalkR:1118191001731874856> Grouping: total of {count} messages."
            ),
            ctx,
        )
        if ctx
        else None
    )
    firsttime, now = (
        datetime.fromtimestamp(0).replace(tzinfo=timezone.utc),
        datetime.now(),
    )
    length, old_group_id = count, group_id
    to_send, current_chana = [], None
    stopcount = 0
    countlim = 2**64
    while new_count < count:
        DatabaseSingleton("voc").commit()
        get_msg_result = ArchivedRPMessage().get_messages_without_group(server_id, 1)
        thesemessages = ArchivedRPMessage().get_messages_within_minute_interval(
            server_id, get_msg_result[0].created_at, forceinterval
        )
        thiscount = len(thesemessages)
        first = thesemessages[0]
        last = thesemessages[-1]
        toprint = f"Now at: {new_count}/{count}. [{first.simplerep()}]-{thiscount}-[{last.simplerep()}]"
        gui.dprint(toprint)
        stopcount += 1
        if stopcount > countlim:
            raise RecursionError("something has gone horribly wrong.")
        if status_mess:
            await status_mess.editw(
                min_seconds=15,
                content=f"<a:LetWalkR:1118191001731874856> {toprint}.<a:LetWalkR:1118191001731874856> ",
            )

        # for m in thesemessages: backlog.put(m)
        ts, group_id = await iterate_backlog(thesemessages, group_id, thiscount)

        DatabaseSingleton("voc").commit()
        await asyncio.sleep(0.1)
        to_send += ts

        new_count += thiscount
        gui.dprint(f"Now at: {new_count}/{count}.")
        await asyncio.sleep(0.1)

    length, old_group_id = count, group_id
    to_send, current_chana, backlog, chars_in_backlog = [], None, Queue(), set()

    DatabaseSingleton("voc").commit()

    # ts, group_id = await iterate_backlog(backlog, group_id, length)
    if status_mess:
        await status_mess.delete()

    to_send += ts

    return length, group_id
