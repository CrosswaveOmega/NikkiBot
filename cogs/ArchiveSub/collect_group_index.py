import asyncio
from typing import List
import gui
from datetime import datetime, timedelta, timezone
from .archive_database import ArchivedRPMessage, ChannelSep, HistoryMakers
from database import DatabaseSingleton
from queue import Queue
import time
from bot import StatusEditMessage
from utility import (
    seconds_to_time_string,
    urltomessage,
    Timer,
)

"""

Groups the collected history messages into "ChannelSep" objects, that store the location and time of each set of 
server message.

"""
DEBUG_MODE = False


async def iterate_backlog(backlog: List[ArchivedRPMessage], group_id: int, count=0):
    # Goes through queue once.
    now = time.monotonic()
    initial = len(backlog)
    archived = 0

    buckets = {}  # Dictionary to hold buckets of messages
    finished_buckets = []  # Dictionary to hold finished buckets
    chars = {}
    for hm in backlog:
        channelind = hm.get_chan_sep()
        if (time.monotonic() - now) > 0.4:
            gui.gprint("pausing for a spell")
            await asyncio.sleep(0.1)
            now = time.monotonic()
        # Find the bucket for the current channel separator
        bucket = buckets.get(channelind)

        if bucket and chars.get(hm.author, None):
            # The bucket is valid and the author is not in this bucket.
            # Make sure it's not this one.
            if chars[hm.author]["ci"] != channelind:
                # It's not this bucket.  Check if this bucket is newer,
                # if it isn't Then time to split.
                if chars[hm.author]["gid"] > bucket["group_id"]:
                    # The bucket the author is inside is NEWER than
                    # the current bucket.  Time to fix that.
                    finished_buckets.append(buckets[channelind])
                    group_id += 1
                    bucket = {"messages": 0, "authors": 0, "group_id": group_id}
                    buckets[channelind] = bucket

                    hm.update(channel_sep_id=buckets[channelind]["group_id"])
                    ChannelSep.add_channel_sep_if_needed(
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
            ChannelSep.add_channel_sep_if_needed(hm, buckets[channelind]["group_id"])

        # Update the channel separator ID of the message
        hm.update(channel_sep_id=buckets[channelind]["group_id"])
        archived += 1
        chars[hm.author] = {"ci": channelind, "gid": buckets[channelind]["group_id"]}
        # Add the message to the bucket
        bucket["messages"] += 1
        # bucket['authors'].add(hm.author)

        # await asyncio.sleep(float(0.0001))

    DatabaseSingleton("voc").commit()
    return [], group_id


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
        with Timer() as timer:
            _, group_id = await iterate_backlog(thesemessages, group_id, thiscount)
        gui.gprint(f"Group took {timer.get_time()} for {thiscount} messages")

        DatabaseSingleton("voc").commit()
        await asyncio.sleep(0.05)
        new_count += thiscount
        gui.dprint(f"Now at: {new_count}/{count}.")

    length = count

    DatabaseSingleton("voc").commit()

    # ts, group_id = await iterate_backlog(backlog, group_id, length)
    if status_mess:
        await status_mess.delete()

    return length, group_id
