import asyncio
import gui
from datetime import datetime, timedelta, timezone
from .archive_database import ArchivedRPMessage, ChannelSep, HistoryMakers
from database import DatabaseSingleton
from queue import Queue
from bot import StatusEditMessage
'''

Groups the collected history messages into "ChannelSep" objects, that store the location and time of each set of 
server message.

'''
DEBUG_MODE=False

async def iterate_backlog(backlog: Queue, group_id: int, count=0):
    tosend = []
    now = datetime.now()
    initial = backlog.qsize()
    archived = 0

    buckets = {}  # Dictionary to hold buckets of messages
    finished_buckets = []  # Dictionary to hold finished buckets
    all_characters=set()
    flags=set()
    chars={}
    while not backlog.empty():
        if DEBUG_MODE:
            gui.gprint(f"Backlog Pass {group_id}:")
        
        if (datetime.now() - now).total_seconds() > 1:
            gui.gprint(f"Backlog Pass {group_id}: {archived} out of {initial} messages, with {count} remaining.")
            #await asyncio.sleep(0.02)
            now = datetime.now()

        hm = backlog.get()
        channelind = hm.get_chan_sep()

        # Find the bucket for the current channel separator
        bucket = buckets.get(channelind)

        if bucket:
            # Check if the author is in any bucket
            if chars.get(hm.author,None):
                #This author is in a bucket.  Make sure it's not this one.
                if chars[hm.author]['ci']!=channelind:
                    #It's not this bucket.  Check if this bucket is newer, if it isn't
                    #Then time to split.
                    if chars[hm.author]['gid']>bucket['group_id']:
                        #The bucket the author is inside is NEWER than 
                        #the current bucket.  Time to fix that.
                        finished_buckets.append(buckets[channelind])
                        group_id+=1
                        bucket = {'messages': [], 'authors': set(), 'group_id': group_id}
                        buckets[channelind] = bucket
                        gui.gprint(f"Backlog Pass {group_id}: {archived} out of {initial} messages, making a new bucket for {channelind}")
                    else:
                        gui.gprint(f"Backlog Pass {group_id}: Author is in older bucket, it's ok to overwrite.")

        # If the bucket doesn't exist, create a new one
        if not bucket:
            group_id+=1
            gui.gprint(f"Backlog Pass {group_id}: {archived} out of {initial} messages, making a new bucket for {channelind}")
            bucket = {'messages': [], 'authors': set(), 'group_id': group_id}
            buckets[channelind] = bucket

        # Update the channel separator ID of the message
        hm.update(channel_sep_id=buckets[channelind]['group_id'])
        archived += 1
        HistoryMakers.add_channel_sep_if_needed(hm, buckets[channelind]['group_id'])
        chars[hm.author]={
             'ci':channelind,
             'gid':buckets[channelind]['group_id']
        }
        # Add the message to the bucket
        bucket['messages'].append(hm)
        bucket['authors'].add(hm.author)
        await asyncio.sleep(float(0.01))

    if DEBUG_MODE:
        gui.gprint("Pass complete.")

    DatabaseSingleton('voc').commit()
    return tosend, group_id

async def iterate_backlog_old(backlog:Queue,group_id:int,count=0):
    tosend = []
    now=datetime.now()
    inital=backlog.qsize()
    archived=0
    while backlog.empty()==False:
        if DEBUG_MODE: gui.gprint(F"Backlog Pass {group_id}:")
        new_backlog=Queue()
        charsinotherbacklog = set()
        current_chana = None
        running = True
        if (datetime.now()-now).total_seconds()>1:
            await asyncio.sleep(0.1)
            now=datetime.now()
        while backlog.empty()==False:
            if (datetime.now()-now).total_seconds()>1:
                gui.gprint(F"Backlog Pass {group_id}: {archived} out of {inital} messages, with {count} remaining.")
                await asyncio.sleep(0.1)
                now=datetime.now()
            hm=backlog.get()
            channelind = hm.get_chan_sep()
            if hm.author in charsinotherbacklog and hm.get_chan_sep() == current_chana:
                running=False
                current_chana = 'CHARA_DID_A_SPLIT'
            if current_chana is None:
                group_id += 1
                if DEBUG_MODE: gui.gprint('inb',current_chana,hm.get_chan_sep(),group_id)
                current_chana = channelind
            if channelind == current_chana and running:
                if DEBUG_MODE: gui.gprint('in',current_chana,hm.get_chan_sep(),group_id)
                hm.update(channel_sep_id=group_id)
                archived+=1
                HistoryMakers.add_channel_sep_if_needed(hm,group_id)
            else:
                new_backlog.put(hm)
                charsinotherbacklog.add(hm.author)
        if DEBUG_MODE: gui.gprint("Pass complete.")
        DatabaseSingleton('voc').commit()
        backlog = new_backlog
    return tosend,group_id

async def do_group(server_id, group_id=0, forceinterval=240, withbacklog=240, maximumwithother=200,ctx=None,glimit=999999999,upperlim=None):
    # sort message list by created_at attribute
    gui.gprint("Starting run.")
    newlist =ArchivedRPMessage().get_messages_without_group(server_id,upperlim=upperlim)
    #await asyncio.gather(
    #                    asyncio.to_thread(ArchivedRPMessage().get_messages_without_group,server_id)
    #                )
    length=len(newlist)
    old_group_id=group_id
    # initialize variables
    tosend, charsinbacklog =  [], set()
    cc_count, current_chana = 0, None
    firsttime = datetime.fromtimestamp(0).replace(tzinfo=timezone.utc)
    
    backlog=Queue()
    status_mess=None
    bksize=0
    now=datetime.now()
    # iterate through the sorted message list
    for e,hm in enumerate(newlist):
        if (datetime.now()-now).total_seconds()>1:
                gui.gprint(f"Now at: {e}/{length}, group_id:{group_id}.")
                await asyncio.sleep(0.1)
                now=datetime.now()
        if status_mess: #This will ensure that the script won't have a 'heart attack' while processing large messages.
            gui.gprint(f"Now at: {e}/{length}, group_id:{group_id}.")
            #await status_mess.editw(min_seconds=20,content=f"Now at: {e}/{length}, group_id:{group_id}.")
        if DEBUG_MODE: gui.gprint('i',hm)
        mytime=(hm.created_at).replace(tzinfo=timezone.utc)
        # create string to identify category, channel, thread combo
        chanin = hm.get_chan_sep()
        hm.is_active=False
        #f"{hm.category}-{hm.channel}-{hm.thread}"
        # calculate time elapsed since first message
        timedel = mytime - firsttime
        minutes = timedel.total_seconds() // 60
        
        # check if a new group should be started
        split=False
        if cc_count > maximumwithother and current_chana != chanin:
            split = True
        elif hm.author in charsinbacklog and chanin == current_chana:
            split = True
        elif minutes >= withbacklog and (backlog or chanin != current_chana) or minutes >= forceinterval:
            split = True
        else:
            split = False

        # start a new group if split condition is met
        if split: 
            # add backlog messages to tosend list with new group_id
            
            DatabaseSingleton('voc').commit()
            
            ts, group_id = await iterate_backlog(backlog, group_id,length-e)
            await asyncio.sleep(0.1)
            tosend += ts
            # reset backlog and character set
            backlog, charsinbacklog = Queue(), set()
            # reset character count and current channel
            cc_count, current_chana = 0, None
            # set new first time to current message time rounded down to nearest 15-minute interval
            firsttime = mytime - (mytime - datetime.min.replace(tzinfo=timezone.utc)) % timedelta(minutes=15)

        # if current_chana is None, set it to the current channel
        if current_chana is None:
            current_chana = hm.get_chan_sep()
            
            if (group_id-old_group_id)>glimit:
                #early termination, for lazygrab
                DatabaseSingleton('voc').commit()
                bksize=0
                ts, group_id = await iterate_backlog(backlog, group_id,length)
                tosend += ts
                print('done')
                return tosend, group_id
            if DEBUG_MODE: gui.gprint('inb',current_chana,hm.get_chan_sep(),group_id)
            group_id+=1
        # add message to current group if it belongs to the current channel
        
        if chanin == current_chana:
            if DEBUG_MODE: gui.gprint('in',current_chana,hm.get_chan_sep(),group_id)
            hm.update(channel_sep_id=group_id)
            HistoryMakers.add_channel_sep_if_needed(hm,group_id)
            cc_count += 1
        # otherwise add message to backlog and add author to character set
        else:
            backlog.put(hm)
            bksize+=1
            charsinbacklog.add(hm.author)
    #Commit to database.
    DatabaseSingleton('voc').commit()
    # add remaining backlog messages to tosend list
    
    ts, group_id = await iterate_backlog(backlog, group_id,length)
    #ChannelSep.derive_channel_seps_mass(server_id)
    tosend += ts

    return length, group_id

    
