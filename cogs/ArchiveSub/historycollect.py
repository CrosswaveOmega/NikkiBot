from datetime import datetime, timedelta, timezone
from .archive_database import HistoryMakers
from database import ServerArchiveProfile
from queue import Queue


'''
Collects all messages in non-blacklisted channels, and adds them to the database in batches of 10.

'''
async def collect_server_history(ctx, update=False,bot_messages_only=True,user_messages_only=False):
        #Collect from desired channels to a point.
        bot=ctx.bot
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        profile=ServerArchiveProfile.get_or_new(guildid)

        messages=[]
        statusMess=bot.add_status_message(channel)
        statusMess.update("I'm getting everything in the given RP channels, this may take a moment!")
        time=profile.last_archive_time
        if time==None: time=0
        last_time=datetime.fromtimestamp(time,timezone.utc)
        new_last_time=last_time.timestamp()
        
        await channel.send("Starting at time:{}".format(last_time.now.strftime("%B %d, %Y %I:%M:%S %p")))

        chancount,ignored,chanlen=0,0,len(guild.text_channels)
        async def iter_hist_messages(cobj, last_time, statusMess, bot_messages_only, user_messages_only,chancount,chanlen):
            characterlen=0
            new_last_time=last_time.timestamp()
            messages=[]
            mlen=0
            async for thisMessage in cobj.history(limit=200000000000000):
                if(thisMessage.created_at<=last_time and update): break 
                add_check=False
                if bot_messages_only: add_check= (thisMessage.author.bot) and (thisMessage.author.id != bot.user.id)
                if user_messages_only: add_check= not (thisMessage.author.bot)
                if bot_messages_only and user_messages_only:    add_check=True
                if add_check:
                    thisMessage.content=thisMessage.clean_content
                    new_last_time=max(thisMessage.created_at.timestamp(),last_time)
                    characterlen+=len(thisMessage.content)
                    messages.append(thisMessage)
                    mlen+=1
                else:
                    ignored=ignored+1
                if(len(messages)%10 == 0 and len(messages)>0):
                    hmes=await HistoryMakers.get_history_message_list(messages)
                    messages=[]
                if(mlen%200 == 0 and mlen>0):
                    await statusMess.updatew(f"{mlen} messages so far in this channel, this may take a moment.   \n On channel {chancount}/{chanlen},\n {cobj.name},\n gathered <a:Loading:812758595867377686>.  This will take a while...")
            if messages:
                hmes=await HistoryMakers.get_history_message_list(messages)
                messages=[]
            return messages, statusMess, characterlen, new_last_time
                
            

        current_channel_count=0
        current_channel_every=max(chanlen//50,1)
        totalcharlen=0
        
        for chan in guild.text_channels:
            chancount+=1
            if profile.has_channel(chan.id)==False and chan.permissions_for(guild.me).view_channel==True and chan.permissions_for(guild.me).read_message_history==True:
                print(chan.name, "id",chan.id," Message Len:",len(messages))
                threads=chan.threads
                archived=[]
                async for thread in chan.archived_threads():
                    archived.append(thread)
                threads=threads+archived
                for thread in threads:
                    mess, statusMess, charlen, newtime=await iter_hist_messages(thread, last_time,statusMess, bot_messages_only, user_messages_only, chancount,chanlen)
                    totalcharlen+=charlen
                    messages=messages+mess
                    current_channel_count+=1

                            
                chanmess, statusMess, charlen, newtime=await iter_hist_messages(chan, last_time,statusMess, bot_messages_only, user_messages_only,  chancount,chanlen)
                new_last_time=max(new_last_time,newtime)
                totalcharlen+=charlen
                messages=messages+chanmess
                current_channel_count+=1
                if current_channel_count >current_channel_every:
                    await statusMess.updatew(f"On channel {chancount}/{chanlen},\n {chan.name},\n gathered <a:Loading:812758595867377686>")
                    current_channel_count=0
            else:
                ignored+=1

        if statusMess!=None: statusMess.delete()
        profile.update(last_archive_time=new_last_time)
        bot.database.commit()

        return messages, totalcharlen