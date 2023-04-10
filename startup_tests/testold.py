from datetime import datetime, timezone, timedelta
from queue import Queue
import random

import sqlite3

# Create a connection to the database
conn = sqlite3.connect('mydatabase.db')
c = conn.cursor()

createtables='''
DROP TABLE IF EXISTS ArchivedRPMessage;
DROP TABLE IF EXISTS ChannelSeps;
CREATE TABLE ArchivedRPMessage (
    message_id INTEGER PRIMARY KEY,
    author TEXT NOT NULL,
    avatar TEXT,
    content TEXT NOT NULL,
    created_at DATETIME,
    channel TEXT NOT NULL,
    category TEXT NOT NULL,
    thread TEXT NOT NULL,
    posted_url TEXT,
    channel_sep_id INTEGER,
    server_id INTEGER NOT NULL,
    FOREIGN KEY(channel_sep_id) REFERENCES ChannelSeps(channel_sep_id)
);

CREATE TABLE ChannelSeps (
    channel_sep_id INTEGER NOT NULL,
    server_id INTEGER NOT NULL,
    chan_sep TEXT NOT NULL,
    created_at TEXT NOT NULL,
    channel TEXT NOT NULL,
    category TEXT NOT NULL,
    thread TEXT NOT NULL,
    posted_url TEXT,
    PRIMARY KEY (channel_sep_id,server_id)
);

-- Create the trigger
CREATE TRIGGER IF NOT EXISTS update_channel_sep_id
AFTER UPDATE OF channel_sep_id ON ArchivedRPMessage
BEGIN
    -- Insert a new entry into ChannelSeps with the updated channel_sep_id
    INSERT INTO ChannelSeps (channel_sep_id, server_id, channel, category, thread, created_at, posted_url)
    SELECT NEW.channel_sep_id, NEW.server_id, NEW.channel, NEW.category, NEW.thread, NEW.created_at, NEW.posted_url
    WHERE NOT EXISTS (
        SELECT 1 FROM ChannelSeps WHERE channel_sep_id = NEW.channel_sep_id
    );
END;
'''

c.executescript(createtables);
conn.commit()


# Define a function to insert an ArchivedRPMessage object into the database
def insert_archived_rp_message(message):
    # Insert the ArchivedRPMessage object
        hmes=vars(message)
        id=hmes['server_id']
        ms=ArchivedRPMessage().add_or_update(**hmes)
    # c.execute("INSERT INTO ArchivedRPMessage(message_id, author, avatar, content, created_at, channel, category, thread, posted_url, server_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    #           (message.message_id, message.author, message.avatar, message.content, message.created_at, message.channel, message.category, message.thread, message.posted_url, message.server_id))
    # conn.commit()
    # print("Inserted successfully!")

# Define a function to update the channel_sep_id of an ArchivedRPMessage object
def update_archived_rp_message(message_id, new_channel_sep_id):
    # Update the channel_sep_id of the corresponding ArchivedRPMessage object
    c.execute("UPDATE ArchivedRPMessage SET channel_sep_id=? WHERE message_id=?", (new_channel_sep_id, message_id))
    conn.commit()
    print("Updated successfully!")
class ArchivedRPMessage:
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
        self.chan_sep = f"{category}-{channel}-{thread}"
        self.channel_sep_id=0
        self.server_id = server_id
    def __repr__(self):
        return f"{self.author}: {self.content} [{self.created_at}] ([{self.chan_sep}]: [{self.channel_sep_id}])"

class ChannelSeps:
    def __init__(self, channel_sep_id, server_id, channel, category, thread,created_at):
        self.channel_sep_id = channel_sep_id
        self.server_id = server_id
        self.chan_sep = f"{category}-{channel}-{thread}"
        self.created_at = created_at
        self.channel = channel
        self.category = category
        self.thread = thread
        self.posted_url = None
    def __repr__(self):
        return f"{self.channel_sep_id}: [{self.chan_sep}]"


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
group_count=0

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
            print(backlog.qsize())
            mycount=0
            charsinotherbacklog=[]
            while backlog.empty()==False:
                hm=backlog.get()
                me=hm
                if me.author in charsinotherbacklog and hm.chan_sep==current_chana:
                    current_chana="CHARA_DID_A_SPLIT"
                    print("Chara did a split.")
                if current_chana == "None":
                    current_chana=hm.chan_sep
                    firsttimea=me.created_at
                    chansep,mycount=post_channel_embed(hm)
                    tosend.append(chansep)#{"type":"sep","val":chansep})
                if hm.chan_sep == current_chana:
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
        print(f"DAYS BETWEEN: {orddays}")
        print("Minutes:",minutes ," current_channel is",current_chan)
        cc_split=False
        if (cc_count>split_vars["maximumwithother"]):
            if(diff_channel):
                cc_split=True
            else:
                print("CHAIN TIME!!!")
        if (me.author in charsinbacklog) and (hm.chan_sep==current_chan):
            print("THIS CHARACTER WAS FOUND IN THE BACKLOG")
            split=True
        
        backcheck=(minutes>=split_vars["withbacklog"] and (backlogmessages>0 or hm.chan_sep!=current_chan) )
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
            print("Switching to channel:", hm.chan_sep)
            current_chan= hm.chan_sep
            madeat=me.created_at
            firsttime= madeat - (madeat - datetime.min.replace())% timedelta(minutes=30)
            #firsttime=m.created_at
            
            chansep,mycount=post_channel_embed(hm)
            tosend.append(chansep)#{"type":"sep","val":chansep})

        if hm.chan_sep == current_chan:
            hm.channel_sep_id=mycount
            #update_archived_rp_message(hm.message_id,mycount)
            tosend.append(hm)#{"type":"mess","val":hm})
            #await web.postMessageAsWebhook(archive_channel, content, name, avatar)
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


# Generate random instances of ArchivedRPMessage
def make_random(num_messages):
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
        message = ArchivedRPMessage(message_id, author, avatar, content, created_at.strftime('%Y-%m-%d %H:%M:%S'), channel, category, thread, posted_url, server_id)
        messages.append(message)
        insert_archived_rp_message(message)
    return messages

randov=make_random(100)
newsend=to_send_order(randov)
with open('checkmeout.txt','w+') as f:
    for i in newsend:
        f.write(str(i)+"\n")
with open('checkmeout2.txt','w+') as f:
    seps=c.execute("SELECT * FROM ChannelSeps WHERE posted_url IS NULL AND server_id = 12345 ORDER BY channel_sep_id;").fetchall()
    for row in seps:
        channel_sep_id, server_id, channel, category, thread, created_at, posted_url = row
        created_at = datetime.datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
        channel_seps_obj = ChannelSeps(channel_sep_id, server_id, channel, category, thread, created_at)
        f.write(str(channel_seps_obj)+"\n")


        messages=c.execute(f'(SELECT * FROM ArchivedRPMessage WHERE server_id =12345? AND channel_sep_id = {channel_sep_id}) ORDER BY created_at').fetchall()
        for row2 in messages:
        # Initialize an ArchivedRPMessage object from the row
                message_id, author, avatar, content, created_at, channel, category, thread, posted_url, csepid, server_id= row2
                created_at = datetime.datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                archived_rp_message_obj = ArchivedRPMessage(message_id, author, avatar, content, created_at, channel, category, thread, posted_url, server_id)
                archived_rp_message_obj.channel_sep_id=csepid
                f.write(str(archived_rp_message_obj)+"\n")


with open('checkmeout.txt','r') as f:
    with open('checkmeout2.txt','r') as f2:
        r1=f.read()
        r2=f2.read()
        if r1==r2:
            print("EQUAL.")
conn.close()