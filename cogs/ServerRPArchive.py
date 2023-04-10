import discord
import operator
import io
import json
import aiohttp
import asyncio
import csv
#import datetime
from datetime import datetime, timedelta, date, timezone
from sqlalchemy import event

from utility import serverOwner, serverAdmin, seconds_to_time_string, MessageTemplates
from utility import WebhookMessageWrapper as web, urltomessage
from bot import TauCetiBot
from random import randint
from discord.ext import commands, tasks

from discord import Webhook



from discord import app_commands


from database import ServerArchiveProfile
from .ArchiveSub import do_group, collect_server_history
from .ArchiveSub import ChannelSep
class ServerRPArchive(commands.Cog):
    """This class is intended for Discord RP servers that use Tupperbox or another proxy application.."""
    bot :TauCetiBot
    def __init__(self, bot:TauCetiBot):
        self.bot=bot
        self.loadlock=asyncio.Lock()
        self.helptext= \
        """This cog is intended for Discord RP servers that use Tupperbox or another proxy bot.  
        It condences all RP messages into a single channel for the sake of chronological readability,
        while grouping them based on time and channel sent to provide as much context as possible."""
        self.helpdescdf="""
        **Setting Up An Archive Channel**

        " • **;set_archive_channel** `#channel-name`- the first command you should execute, will set the archive channel to here.
        
        """
        


    @commands.command(hidden=False)
    async def channelcount(self, ctx):  
        '''
        Get a count of all channels in your server
        '''
        guild = ctx.message.channel.guild
        acount,ccount,catcount=0,0,0
        for chan in guild.channels:
            acount+=1
            if chan.type==discord.ChannelType.text:
                ccount+=1;
            if chan.type==discord.ChannelType.category:
                catcount+=1;
        await ctx.send("```allchannels:{}, \n Total text channels: {}, \n categories: {}.```".format(acount, ccount, catcount))



    @commands.command(enabled=False)
    async def ignoreusers(self, ctx):
        '''
        WORK IN PROGRESS: IGNORE ARCHIVING FROM THESE USERS.
        '''
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id

        if not(serverOwner(ctx) or serverAdmin(ctx)):
            return False

        profile=ServerArchiveProfile.get_or_new(guildid)
        chanment=ctx.message.mentions
        if len(chanment)>=1:
            for user in chanment:
                print(user.name)
                profile.add_user_to_list(user.id)

        self.bot.database.commit()
    @commands.hybrid_group(fallback="view")
    async def archive_setup(self, ctx):
        """Setup the RP archival system here."""

        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        profile=ServerArchiveProfile.get_or_new(guildid)

        await MessageTemplates.server_archive_message(ctx,"Here is your server's data.")


    @archive_setup.command(name="set_archive_channel", brief="set your desired Archive Channel.")
    @app_commands.describe(chanment= "The new archive channel you want to set.")
    async def setArchiveChannel(self, ctx, chanment:discord.TextChannel):  # Add ignore.
        '''set your desired archive channel.
        '''

        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        if not(serverOwner(ctx) or serverAdmin(ctx)):
            return False
        
        profile=ServerArchiveProfile.get_or_new(guildid)
        print(profile)

        newchan_id=chanment.id
        profile.add_or_update(guildid,history_channel_id=newchan_id)

        bot.database.commit()
        
        await MessageTemplates.server_archive_message(ctx,"The Server Archive Channel has been set.")


    @archive_setup.command(
        name="add_ignore_channels",
        brief="start ignoring mentioned #channels while archiving"
    )
    async def addToIgnoredChannels(self, ctx):  # Add ignore.
        '''
        Adds all mentioned channels to this server's ignore list. Ignored channels will not be archived.
        '''
        bot = ctx.bot
        thismessage=ctx.message
        auth = ctx.message.author
        channel = ctx.message.channel
        def check(m):
            return m.author==auth and m.channel == channel
        if ctx.interaction:
            await ctx.send("Due to app command limitations, please specify all the channels you want to ignore in another message below.")
            try:
                msg = await bot.wait_for('message', timeout=60.0*15, check=check)
                thismessage=msg
            except asyncio.TimeoutError:
                await ctx.send('You took way too long.')
                return
            else:
                pass

        guild=channel.guild
        guildid=guild.id

        if not(serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(ctx,"You do not have permission to use this command.")
            return False
        profile=ServerArchiveProfile.get_or_new(guildid)
        chanment=thismessage.channel_mentions
        if len(chanment)>=1:
            for chan in chanment:
                profile.add_channel(chan.id)
        else:
            await MessageTemplates.server_archive_message(ctx,"You mentioned no channels...")
            return 
        self.bot.database.commit()
        await MessageTemplates.server_archive_message(ctx,"Added channels to my ignore list.  Any messages in these channels will be ignored while archiving.")

        


    @archive_setup.command(
        
        name="remove_ignore_channels",
        brief="stop ignoring mentioned #channels during archival"
    )
    async def removeFromIgnoredChannels(self, ctx):  # Add card.
        '''
        remove channels from the ignore list. Use the #channel-name format.
        '''
        bot = ctx.bot
        thismessage=ctx.message
        auth = ctx.message.author
        channel = ctx.message.channel
        def check(m):
            return m.author==auth and m.channel == channel
        if ctx.interaction:
            await ctx.send("Due to app command limitations, please specify all the channels you want to stop ignoring in another message below.")
            try:
                msg = await bot.wait_for('message', timeout=60.0*15, check=check)
                thismessage=msg
            except asyncio.TimeoutError:
                await channel.send('You took way too long.')
                return
            else:
                pass
        guild=channel.guild
        guildid=guild.id

        if not(serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(ctx,"You do not have permission to use this command.")
            return False
        profile=ServerArchiveProfile.get_or_new(guildid)
        chanment=thismessage.channel_mentions
        if len(chanment)>=1:
            for chan in chanment:
                profile.remove_channel(chan.id)
        else:
            await MessageTemplates.server_archive_message(ctx,"You mentioned no channels.")
            return 
        self.bot.database.commit()
        await MessageTemplates.server_archive_message(ctx,"Removed channels from my ignore list.  Any messages in these channels will no longer be ignored while archiving.")

    


    @commands.command()
    async def firstlasttimestamp(self, ctx, *args):
        """Get the last timestamp of the most recently archived message.
        """
        mybot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id


        #options.
        update=False
        indexbot=True
        user=False


        for arg in args:
            if arg == 'full':                update=False
            if arg == 'update':                update=True
            if arg== 'ws':                indexbot,user=True,False
            if arg == 'user':                indexbot,user=False,True
            if arg == 'both':                indexbot,user=True,True


        if not(serverOwner(ctx) or serverAdmin(ctx)):  #Permission Check.
            return False


        profile=ServerArchiveProfile.get_or_new(guildid)


        if profile.history_channel_id == 0:
            await channel.send("Set a history channel first.")
            return False

        last_time=datetime.fromtimestamp(profile.last_archive_time,timezone.utc)
        await channel.send("timestamp:{}".format(last_time.timestamp()))




        
    async def edit_embed_and_neighbors(self, target):
        '''
        This code checks if the target ChannelSep object has a 
        posted_url attribute, and then edits it's 
        
        '''
        async def edit_if_needed(target):
            if target:
                message=await urltomessage(target.posted_url,self.bot)
                
                emb,lc=target.create_embed()
                print(lc)
                target.update(neighbor_count=lc)
                await message.edit(embeds=[emb])
        print(target, target.posted_url)
        if target.posted_url:
            iL=target.get_neighbor(False,False,False)
            cL=target.get_neighbor(True,False,False)
            print(iL,cL,target)

            await edit_if_needed(iL)
            await edit_if_needed(cL)
            print(f"New posted_url value for ChannelSep")

    @commands.command( extras={"guildtask":['rp_history']})
    async def compileArchiveChannel(self, ctx, *args):
        """Compile all messages into archive channel.  This can be invoked with options.
            +`full` - get the full history of this server
            +`update` -only update the current archive channel

            +`ws` - compile only webhooks
            +`user` - complile only users
            +`both` -compile both

        """
        mybot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id


        #options.
        update=False
        indexbot=True
        user=False

        archive_from="server"

        await channel.send("KICKSTART THE FRYERS I WANT FOOOD.")



        timebetweenmess=2.5
        characterdelay=0.05


        profile=ServerArchiveProfile.get_or_new(guildid)
        
        for arg in args:
            if arg == 'full':   update=False
            if arg == 'update': update=True
            if arg== 'ws':      indexbot,user=True,False
            if arg == 'user':   indexbot,user=False, True
            if arg == 'both':   indexbot,user=True,True
        await channel.send(profile.history_channel_id)
        if profile.history_channel_id == 0:
            await channel.send("Set a history channel first.")
            return False
        archive_channel=guild.get_channel(profile.history_channel_id)


        dynamicwait=False

        statusMess=mybot.add_status_message(ctx)

        messages=[]
        MessageTemplates(ctx.Guild,)
        await statusMess.updatew("Collecting server history...")

        totalcharlen=0
        if archive_from=="server":
           messages, totalcharlen=await collect_server_history(ctx,update,indexbot,user)
        
        await statusMess.updatew("Your messages are pre-sorted.")


        
        await statusMess.updatew("Grouping into separators, this may take a while.")
        #CREATE LIST OF MESSAGES.
        lastgroup=profile.last_group_num
        ts,group_id=await do_group(guildid,profile.last_group_num)
        fullcount=ts
        profile.update(last_group_num=group_id)
        remaining_time_float= fullcount* timebetweenmess
        print(lastgroup,group_id)
        if dynamicwait:
            remaining_time_float+=(totalcharlen*characterdelay)

        await statusMess.updatew(f"This is going to take about...{seconds_to_time_string(int(remaining_time_float))}")
        

        grouped=ChannelSep.get_separators_without(guildid)
        for sep in grouped:
            currjob="rem: {}".format(seconds_to_time_string(int(remaining_time_float)))
            emb,count=sep.create_embed()
            chansep=await archive_channel.send(embed=emb)
            sep.update(posted_url=chansep.jump_url)
            
                    
            await self.edit_embed_and_neighbors(sep)
            self.bot.database.commit()
            for amess in sep.get_messages():
                c,au,av=amess.content,amess.author,amess.avatar
                files=[]
                for attach in amess.list_files():
                    this_file=attach.to_file()
                    files.append(this_file)
                #print(archive_channel, c, au, av, [],files)
                kwargs={
                    ''
                }
                webhookmessagesent=await web.postWebhookMessageProxy(archive_channel, message_content=c, display_username=au, avatar_url=av, embed=[], file=files)
                if webhookmessagesent:

                    #print(webhookmessagesent)
                    amess.update(posted_url=webhookmessagesent.jump_url)
                    
                if dynamicwait:
                    chars=len(c)
                    await asyncio.sleep(characterdelay*chars)
                    await asyncio.sleep(timebetweenmess)
                    remaining_time_float=remaining_time_float-(timebetweenmess+characterdelay*chars)
                else:
                    await asyncio.sleep(timebetweenmess)
                    remaining_time_float=remaining_time_float-(timebetweenmess)
            self.bot.database.commit()
            await statusMess.updatew(f"This is going to take about...{seconds_to_time_string(int(remaining_time_float))}")
        statusMess.delete()     
        self.bot.database.commit()
        await ctx.send("I finished the archive!  ")
        print("Done.")


    @commands.command( extras={"guildtask":['rp_history']})
    async def makeCalendar(self, ctx, *args):
        ##NEXT.  OH GOD.
        """Create a calendar of all messages with dates into your history channel."""
        bot = ctx.bot
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id

        profile=ServerArchiveProfile.get_or_new(guildid)
        

        await channel.send(profile.history_channel_id)
        if profile.history_channel_id == 0:
            await channel.send("Set a history channel first.")
            return False
        archive_channel=guild.get_channel(profile.history_channel_id)

        async def calendarMake(separator_messages, lastday=None, this_dates=["█","█","█","█","█","█","█"], current_calendar_embed_object=None, weeknumber=0):
            daystarts=[]
            day_count=0
            separator_count=0

            lastmessage=None
            lastdate=None

            for num, spot in enumerate(separator_messages, start=0):
                thisMessage=spot
                curr_count=len(thisMessage.get_messages())

                thisembed,c=thisMessage.create_embed()
                newdate=thisembed.timestamp

                if lastdate==None:
                    lastdate=newdate.date()
                elif (newdate.date()-lastdate).days>0:
                    daystarts.append({"date":lastdate, "url":lastmessage.posted_url, "mcount":day_count, "sepcount":separator_count})
                    lastdate=newdate.date()
                    day_count=0
                    separator_count=0
                print((lastdate-newdate.date()).days)
                lastmessage=thisMessage
                day_count=day_count+curr_count
                separator_count=separator_count+1

            daystarts.append({"date":lastdate, "url":lastmessage.posted_url, "mcount":day_count, "sepcount":separator_count})
            ########################################## MAKING THE CALENDAR ############################3
            #lastday=None
            def same_week(currdat, last):
                '''returns true if a dateString in %Y%m%d format is part of the current week'''
                d1 = currdat
                d2 = last
                return d1.isocalendar()[1] == d2.isocalendar()[1] \
                          and d1.year == d2.year
            def same_month(currdat, last):
                '''returns true if a dateString in %Y%m%d format is part of the current week'''
                d1 = currdat
                d2 = last
                return (d1.month== d2.month and d1.year == d2.year)

            #discord.Embed(title=date.strftime("%B %Y"), colour=discord.Colour(randint(0,0xffffff)))
            print("Current Calendar Embed")

            for day in daystarts:
                date=day["date"]
                url=day["url"]
                mcount=day["mcount"]
                sepcount=day["sepcount"]
                if current_calendar_embed_object==None:
                    current_calendar_embed_object=discord.Embed(title=date.strftime("%B %Y"), colour=discord.Colour(randint(0,0xffffff)))
                if lastday != None:
                    if not same_week(lastday, date):
                        current_calendar_embed_object.add_field(name="Week {}".format(weeknumber), value="\n".join(this_dates), inline=True)
                        this_dates=["█","█","█","█","█","█","█"]
                        weeknumber=weeknumber+1
                    if not same_month(lastday, date):
                        await web.postWebhookMessageProxy(archive_channel, message_content="_ _", display_username="DateMaster", avatar_url=bot.user.avatar.url, embed=[current_calendar_embed_object])
                        current_calendar_embed_object=discord.Embed(title=date.strftime("%B %Y"), colour=discord.Colour(randint(0,0xffffff)))
                        weeknumber=0
                else:
                    current_calendar_embed_object=discord.Embed(title=date.strftime("%B %Y"), colour=discord.Colour(randint(0,0xffffff)))
                strday=date.strftime("%m-%d-%Y")
                this_dates[date.weekday()]="[{}]({})-{}".format(strday, url, mcount)
                lastday=date
            current_calendar_embed_object.add_field(name="Week {}".format(weeknumber), value="\n".join(this_dates), inline=True)
            await web.postWebhookMessageProxy(archive_channel, message_content="_ _", display_username="DateMaster", avatar_url=bot.user.avatar.url, embed=[current_calendar_embed_object])

        await calendarMake(ChannelSep.get_all_separators(guildid))
        



async def setup(bot):
    await bot.add_cog(ServerRPArchive(bot))



async def teardown(bot):
    await bot.remove_cog('ServerRPArchive')
