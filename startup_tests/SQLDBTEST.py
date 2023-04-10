

from discord import Webhook

from datetime import datetime, timezone, timedelta
from queue import Queue
import random


from discord import app_commands
from discord.app_commands import Choice


import sqlite3
from database import DatabaseSingleton
from database import ServerArchiveProfile

from sqlalchemy import create_engine, MetaData
# Define a function to insert an ArchivedRPMes object into the database
def insert_archived_rp_message(ars,message):
    # Insert the ArchivedRPMes object
        hmes=vars(message)
        #print(hmes)
        id=hmes['server_id']
        ms=ars.add_or_update(**hmes)
    # c.execute("INSERT INTO ArchivedRPMes(message_id, author, avatar, content, created_at, channel, category, thread, posted_url, server_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    #           (message.message_id, message.author, message.avatar, message.content, message.created_at, message.channel, message.category, message.thread, message.posted_url, message.server_id))
    # conn.commit()
    # print("Inserted successfully!")

# Define a function to update the channel_sep_id of an ArchivedRPMes object
#def update_archived_rp_message(message_id, new_channel_sep_id):
    # Update the channel_sep_id of the corresponding ArchivedRPMes object
    #c.execute("UPDATE ArchivedRPMes SET channel_sep_id=? WHERE message_id=?", (new_channel_sep_id, message_id))
    #conn.commit()
    #print("Updated successfully!")
class ArchivedRPMes:
    def __init__(self, message_id, author, avatar, content, created_at, channel, category, thread, posted_url, server_id):
        self.message_id = message_id
        self.author = author
        self.avatar = avatar
        self.content = content
        self.created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
        self.channel = channel
        self.category = category
        self.thread = thread
        self.posted_url = posted_url
        self.channel_sep_id=None
        self.server_id = server_id

    def get_chan_sep(self):
        return f"{self.category}-{self.channel}-{self.thread}"
    def __repr__(self):
        return f"{self.author}: {self.content} [{self.created_at}] ([{self.get_chan_sep()}]: [{self.channel_sep_id}])"

class ChannelSeps:
    def __init__(self, channel_sep_id, server_id, channel, category, thread,created_at):
        self.channel_sep_id = channel_sep_id
        self.server_id = server_id
        self.created_at = created_at
        self.channel = channel
        self.category = category
        self.thread = thread
        self.posted_url = None

    def get_chan_sep(self):
        return f"{self.category}-{self.channel}-{self.thread}"
    def __repr__(self):
        return f"{self.channel_sep_id}: [{self.get_chan_sep()}]"


# Sample data for randomization
authors = ["Alice", "Bob", "Charlie", "David"]
avatars = ["https://example.com/avatar1.png", "https://example.com/avatar2.png", "https://example.com/avatar3.png"]
contents = ["Hello, world!", "Lorem ipsum dolor sit amet", "This is a test message"]
channels = ["general", "random", "programming"]
categories = ["chat"]
threads = ["thread1"]
posted_urls = ["https://example.com/post1", "https://example.com/post2", "https://example.com/post3"]
server_id = 12345
global group_count
group_count=-1

def to_send_order(message_unsorted):
    "Create an ordered list of messages to add to the history log."


    split_vars={
        "forceinterval":240,
        "withbacklog":240,
        "maximumwithother":200

    }
    newlist = sorted(message_unsorted, key=lambda x: x.created_at.timestamp(), reverse=False)

    backlog=Queue()
    current_chan="None"
    firsttime= datetime.fromtimestamp(0)
    cc_count=0
    #last_channel_sep'

    tosend=[]
    sent_message_cache=[];
    
    def post_channel_embed(hm:str):
        "create a channel separator embed, add to list."
        global group_count
        group_count+=1
        channel_sep=ChannelSeps(group_count,hm.server_id,hm.channel,hm.category,hm.thread,created_at=hm.created_at)
        
        return (channel_sep,group_count)

    def iterate_backlog(backlog, lastchannelsep=None, actors=[]): #iterate through the backlog queue, grouping in the same way as the primary
        while backlog.empty()==False: #iterate backlog
            new_backlog=Queue()
            current_chana="None"
            firsttimea=datetime.fromtimestamp(0,timezone.utc)
            #print(backlog.qsize())
            mycount=0
            charsinotherbacklog=[]
            while backlog.empty()==False:
                hm=backlog.get()
                me=hm
                if me.author in charsinotherbacklog and hm.get_chan_sep()==current_chana:
                    current_chana="CHARA_DID_A_SPLIT"
                    #print("Chara did a split.")
                if current_chana == "None":
                    current_chana=hm.get_chan_sep()
                    firsttimea=me.created_at
                    chansep,mycount=post_channel_embed(hm)
                    tosend.append(chansep)#{"type":"sep","val":chansep})
                if hm.get_chan_sep() == current_chana:
                    hm.channel_sep_id=mycount
                    #update_archived_rp_message(hm.message_id,mycount)
                    tosend.append(hm)#"type":"mess","val":hm})

                else:
                    new_backlog.put(hm)
                    charsinotherbacklog.append(me.author)
            backlog=new_backlog

    diff_channel=False


    charsinbacklog=[];
    backlogmessages=0

    thistime=None
    mycount=0
    for hm in newlist:
        me=hm

        split=False

        timedel=(me.created_at - firsttime)
        this_time=me.created_at.astimezone(timezone.utc)
        orddays=firsttime.date().toordinal()-this_time.date().toordinal()
        second_total=timedel.total_seconds()
        minutes=second_total//60
        #print(f"DAYS BETWEEN: {orddays}")
        #print("Minutes:",minutes ," current_channel is",current_chan)
        cc_split=False
        if (cc_count>split_vars["maximumwithother"]):
            if(diff_channel):
                cc_split=True
            else:
                pass
                #print("CHAIN TIME!!!")
        if (me.author in charsinbacklog) and (hm.get_chan_sep()==current_chan):
            #print("THIS CHARACTER WAS FOUND IN THE BACKLOG")
            split=True
        
        backcheck=(minutes>=split_vars["withbacklog"] and (backlogmessages>0 or hm.get_chan_sep()!=current_chan) )
        if (cc_split) or backcheck or (minutes>=split_vars["forceinterval"]) : #Split condition.
            split=True
        if split:
            #split.
            iterate_backlog(backlog)
            cc_count=0
            current_chan="None"
            madeat=me.created_at
            firsttime= madeat - (madeat - datetime.min.replace())% timedelta(minutes=15)
            
            #time remaining.

            
            #await mybot.change_presence(activity=game)
            charsinbacklog=[]
            backlogmessages=0
            #done updating time.


        if current_chan == "None":
            #print("Switching to channel:", hm.get_chan_sep())
            current_chan= hm.get_chan_sep()
            madeat=me.created_at
            firsttime= madeat - (madeat - datetime.min.replace())% timedelta(minutes=30)
            #firsttime=m.created_at
            
            chansep,mycount=post_channel_embed(hm)
            tosend.append(chansep)#{"type":"sep","val":chansep})

        if hm.get_chan_sep() == current_chan:
            hm.channel_sep_id=mycount
            #update_archived_rp_message(hm.message_id,mycount)
            tosend.append(hm)#{"type":"mess","val":hm})
            #await web.postWebhookMessageProxy(archive_channel, content, name, avatar)
            cc_count=cc_count+1
            diff_channel=False
        else:
            backlog.put(hm)
            if not me.author in charsinbacklog:
                charsinbacklog.append(me.author)
            backlogmessages+=1
            diff_channel=True
    iterate_backlog(backlog)
    return tosend






def hgatgertest():
    
    s=DatabaseSingleton("START", db_name='./footester.db')
    from cogs.ArchiveSub import create_history_pickle_dict, ChannelSep, ArchivedRPMessage, ArchivedRPFile, DummyFile, HistoryMakers, do_group
    guildid=1071087693481652224


    ent=ServerArchiveProfile().get_entry(guildid)
    print(ent)
    # Generate random instances of ArchivedRPMessage
    def make_random(num_messages, server_id):
        messages = []
        now=datetime.now() 
        for i in range(num_messages):
            message_id = i + 1
            author = random.choice(authors)
            avatar = random.choice(avatars)
            content = random.choice(contents)
            created_at = now - timedelta(minutes=random.randint(0, 59), seconds=random.randint(0, 59))
            channel = random.choice(channels)
            category = random.choice(categories)
            thread = random.choice(threads)
            posted_url = random.choice(posted_urls)
            message = ArchivedRPMes(message_id, author, avatar, content, created_at.strftime('%Y-%m-%d %H:%M:%S'), channel, category, thread, posted_url, server_id)
            messages.append(message)
            insert_archived_rp_message(ArchivedRPMessage, message)
        return messages
    newchan_id=1092478820646408292
    ServerArchiveProfile().add_or_update(server_id=guildid,history_channel_id=newchan_id)
    randov=make_random(100,guildid)
    newsend=to_send_order(randov)
    s.commit()
    do_group(guildid,group_id=1)
    with open('checkmeout.txt','w+') as f:
        for i in newsend:
            f.write(str(i)+"\n")
    with open('checkmeout2.txt','w+') as f:
        seps=ChannelSep().get_separators_without(guildid)
        print(seps)
        for row in seps:
            print(str(row))
            f.write(str(row)+"\n")


            #messages=c.execute(f'(SELECT * FROM ArchivedRPMes WHERE server_id =12345? AND channel_sep_id = {channel_sep_id}) ORDER BY created_at').fetchall()
            for row2 in row.get_messages():

                    f.write(str(row2)+"\n")

    s.commit()
    s.close_out()

if __name__ == "__main__":
   hgatgertest()
