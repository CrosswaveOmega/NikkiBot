import asyncio
from datetime import datetime, timedelta, timezone
from typing import Tuple
from .archive_database import HistoryMakers
from database import ServerArchiveProfile
import discord
from queue import Queue
from bot import StatusEditMessage

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
        statusMessToEdit=await channel.send("I'm getting everything in the given RP channels, this may take a moment!")

        statmess=StatusEditMessage(statusMessToEdit,ctx)
        time=profile.last_archive_time
        if time: time=time.timestamp()
        if time==None: time=0
        last_time=datetime.fromtimestamp(time,timezone.utc)
        new_last_time=last_time.timestamp()
        
        await channel.send("Starting at time:{}".format(last_time.strftime("%B %d, %Y %I:%M:%S %p")))

        chancount,ignored,chanlen=0,0,len(guild.text_channels)
        async def iter_hist_messages(cobj, last_time, bot_messages_only, user_messages_only,chancount,chanlen):
            characterlen=0
            ignoredhere=0
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
                    new_last_time=max(thisMessage.created_at.timestamp(),new_last_time)
                    characterlen+=len(thisMessage.content)
                    messages.append(thisMessage)
                    mlen+=1
                else:
                    ignoredhere=ignoredhere+1
                if(len(messages)%10 == 0 and len(messages)>0):
                    hmes=await HistoryMakers.get_history_message_list(messages)
                    messages=[]
                if(mlen%200 == 0 and mlen>0):
                    await asyncio.sleep(1)
                    #await edittime.invoke_if_time(content=f"{mlen} messages so far in this channel, this may take a moment.   \n On channel {chancount}/{chanlen},\n {cobj.name},\n gathered <a:Loading:812758595867377686>.  This will take a while...")
                    #await statusMess.updatew(f"{mlen} messages so far in this channel, this may take a moment.   \n On channel {chancount}/{chanlen},\n {cobj.name},\n gathered <a:Loading:812758595867377686>.  This will take a while...")
            if messages:
                hmes=await HistoryMakers.get_history_message_list(messages)
                messages=[]
            return messages, characterlen, new_last_time,ignoredhere
                
            

        current_channel_count=0
        current_channel_every=max(chanlen//50,1)
        totalcharlen=0
        
        for chan in guild.text_channels:
            chancount+=1
            if profile.has_channel(chan.id)==False and chan.permissions_for(guild.me).view_channel==True and chan.permissions_for(guild.me).read_message_history==True:
                threads=chan.threads
                archived=[]
                async for thread in chan.archived_threads():
                    archived.append(thread)
                threads=threads+archived
                for thread in threads:
                    mess, charlen, newtime, ign=await iter_hist_messages(thread, last_time, bot_messages_only, user_messages_only, chancount,chanlen)
                    new_last_time=max(new_last_time,newtime)
                    totalcharlen+=charlen
                    ignored+=ign
                    messages=messages+mess
                    current_channel_count+=1

                            
                chanmess, charlen, newtime,ign=await iter_hist_messages(chan, last_time,bot_messages_only, user_messages_only,  chancount,chanlen)
                new_last_time=max(new_last_time,newtime)
                ignored+=ign
                totalcharlen+=charlen
                messages=messages+chanmess
                current_channel_count+=1
                await statmess.editw(min_seconds=15,content=f"On channel {chancount}/{chanlen},\n {chan.name},\n gathered <a:Loading:812758595867377686>")
                if current_channel_count >current_channel_every:
                    await asyncio.sleep(1)
                    
                    #await edittime.invoke_if_time()
                    current_channel_count=0
            else:
                ignored+=1

        if statusMessToEdit!=None: 
            await statusMessToEdit.delete()
        
        return messages, totalcharlen, new_last_time

def check_channel(historychannel:discord.TextChannel) -> Tuple[bool, str]:
    '''Check if the passed in history channel has the needed permissions to become an auto_channel.'''
    permissions = historychannel.permissions_for(historychannel.guild.me)
    permission_check_string=""
    if not permissions.view_channel:
        permission_check_string="I can't read view this channel.\n "
    if not permissions.read_messages:
        permission_check_string+="I can't read messages here.\n"
    if not permissions.read_message_history:
        permission_check_string+="I can't read message history here.\n"
    if not permissions.send_messages:
        permission_check_string+="I can't send messages.\n "
    if not permissions.manage_messages:
        permission_check_string+="I can't manage messages here.\n"
    if not permissions.manage_webhooks:
        permission_check_string+="I can't manage webhooks here.\n"
    if not permissions.embed_links:
        permission_check_string+="I can't embed links here. \n"
    if not permissions.attach_files:
        permission_check_string+="I can't attach files here.\n"
    if permission_check_string:
        result=f"I have one or more problems with the specified log channel {historychannel.mention}.  {permission_check_string}\n  Please update my permissions for this channel in particular."
        return False, result
    messagableperms=['add_reactions','external_emojis','external_stickers','read_message_history','manage_webhooks' ]
    add="."

    for p, v in permissions:
        if v:
            if p in messagableperms:
                messagableperms.remove(p)
    if len(messagableperms)>0:
        add="I do not think I should archive with the following permissions disabled for that channel: "+",".join(messagableperms)+"."
        return False, add
    return True, "Needed permissions are set in this channel"+add