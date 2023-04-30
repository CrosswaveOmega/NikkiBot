from typing import Literal
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

from utility import serverOwner, serverAdmin, seconds_to_time_string, MessageTemplates, get_time_since_delta
from utility import WebhookMessageWrapper as web, urltomessage, relativedelta_sp
from bot import TCBot, TCGuildTask, Guild_Task_Functions
from random import randint
from discord.ext import commands, tasks

from discord import Webhook



from discord import app_commands


from database import ServerArchiveProfile
from .ArchiveSub import do_group, collect_server_history, check_channel
from .ArchiveSub import ChannelSep


from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU
class ServerRPArchive(commands.Cog):
    """This class is intended for Discord RP servers that use Tupperbox or another proxy application.."""
    def __init__(self, bot):
        self.bot:TCBot=bot
        self.loadlock=asyncio.Lock()
        self.helptext= \
        """This cog is intended for Discord RP servers that use Tupperbox or another proxy bot.  It condences all RP messages (messages sent with a proxy bot such as Tupperbox) sent across a server (ignoring channels when needed) into a single server specific channel, while grouping them into blocks via a specialized algorithm based on the time and category,channel, and thread(if needed) of each rp message.
        
        Please note, in order to work, this command **saves a copy of every archived RP message into a local database.**  
        
        ***Only messages sent by bots and webhooks will be archived!***

        Get started by utilizing the archive_setup family of commands to configure your archive channel and add your ignore channels.
        """

        Guild_Task_Functions.add_task_function("COMPILE",self.gtask_compile)

    
    

    def cog_unload(self):
        #Remove the task function.
        Guild_Task_Functions.remove_task_function("COMPILE")
        pass
    
    def server_profile_field_ext(self,guild):
        '''return a dictionary for the serverprofile template message'''
        profile=ServerArchiveProfile.get(guild.id)
        if not profile:
            return None
        last_date=""
        aid=""
        hist_channel=profile.history_channel_id
        if profile.last_archive_time:
            timestamped=profile.last_archive_time.timestamp()
            last_date=f"<t:{int(timestamped)}:f>"
        if hist_channel: aid=f"<#{hist_channel}>"
        if aid:
            clist=profile.count_channels()
            value=f"Archive Channel: {aid}\n"
            if last_date:
                value+=f"Last Run: {last_date}\n"
            value+=f"Ignored Channels: {clist}\n"
            
            autoentry=TCGuildTask.get(guild.id,"COMPILE")
            res=autoentry.get_status_desc()
            if res:
                value+=res
            field={"name":"Server RP Archive",'value':value}
            return field
        return None



    async def gtask_compile(self, source_message=None):
        if not source_message: return None
        context=await self.bot.get_context(source_message)
        await context.channel.send("Greetings from GTASK.")
        try:
            await context.invoke(self.bot.get_command("compile_archive"))
        except Exception as e:
            er=MessageTemplates.get_error_embed(title=f"Error with AUTO",description=f"{str(e)}")
            await source_message.channel.send(embed=er)
            raise e

    @commands.command(hidden=True)
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

    @app_commands.command(name="compile_sanity_check", description="ensure that the needed permissions for the auto channel are set")
    async def sanity_check(self, interaction: discord.Interaction):
        '''make a poll!'''
        ctx: commands.Context = await self.bot.get_context(interaction)
        bot=ctx.bot
        guild=ctx.guild
        task_name="COMPILE"
        if not(serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(ctx,"You don't have permission to use this command..")
            return False
        
        

        
        old=TCGuildTask.get(guild.id, task_name)
        if old:
            autochannel=bot.get_channel(old.target_channel_id)
            #check if the passed in autochannel meets the standards.
            passok, statusmessage = Guild_Task_Functions.check_auto_channel(autochannel)
            if not passok:
                await MessageTemplates.server_archive_message(ctx,statusmessage, ephemeral=True)
            else:
                await MessageTemplates.server_archive_message(ctx,"Everything should be a-ok")
            
        else:
            await MessageTemplates.server_archive_message(ctx,"You never set up an auto channel!")
        

    @commands.command(enabled=False, hidden=True)
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
        """This family of commands is for setting up your server archive."""
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        profile=ServerArchiveProfile.get_or_new(guildid)

        await MessageTemplates.server_archive_message(ctx,"Here is your server's data.")

    @archive_setup.command(name="set_archive_channel", brief="set a desired Archive Channel.")
    @app_commands.describe(chanment= "The new archive channel you want to set.")
    async def setArchiveChannel(self, ctx, chanment:discord.TextChannel):  # Add ignore.
        '''Use this command to set an Archive Channel.
        '''

        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        if not(serverOwner(ctx) or serverAdmin(ctx)):
            await ctx.send("You do not have permission to use this command.")
            return False
        
        profile=ServerArchiveProfile.get_or_new(guildid)
        print(profile)
        passok, statusmessage = check_channel(chanment)
        if not passok:
            await MessageTemplates.server_archive_message(ctx,statusmessage)
            return

        newchan_id=chanment.id
        profile.add_or_update(guildid,history_channel_id=newchan_id)

        bot.database.commit()
        
        await MessageTemplates.server_archive_message(ctx,"The Server Archive Channel has been set.")

    
    @archive_setup.command(name="enable_auto", brief="automatically archive the server every sunday at 4pm.")
    @app_commands.describe(autochannel= "a channel where the command will run.  not same thing as the archive_channel!")
    async def task_add(self, ctx,autochannel:discord.TextChannel):
        """Add an automatic task."""
        bot=ctx.bot
        guild=ctx.guild
        task_name="COMPILE"
        if not(serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(ctx,"You don't have permission to use this command..")
            return False
        
        #check if the passed in autochannel meets the standards.
        passok, statusmessage = Guild_Task_Functions.check_auto_channel(autochannel)

        if not passok:
            await MessageTemplates.server_archive_message(ctx,statusmessage)
            return
        
        prof=ServerArchiveProfile.get(server_id=guild.id)
        if not prof: 
            await MessageTemplates.server_archive_message(ctx,"...you've gotta set up the archive first...")
            return
        if autochannel.id==prof.history_channel_id:
            result=f"this should not be the same channel as the archive channel.  Specify a different channel such as a bot spam channel."
            await MessageTemplates.server_archive_message(ctx,result)
            return
        
        old=TCGuildTask.get(guild.id, task_name)
        if not old:
            message=await autochannel.send(f"**ATTEMPTING SET UP OF AUTO COMMAND {task_name}**")
            myurl=message.jump_url
            robj=relativedelta_sp(weekday=[SU],hour=17,minute=0,second=0)
            new=TCGuildTask.add_guild_task(guild.id, task_name, message, robj)
            new.to_task(bot)
            
            result=f"The automatic archive system is set up for <#{autochannel.id}>.  See you on Sunday at 5pm est."
            await MessageTemplates.server_archive_message(ctx,result)
        else:
            old.target_channel_id=autochannel.id
            
            message=await autochannel.send("**ALTERING AUTO CHANNEL...**")
            old.target_message_url=message.jump_url
            self.bot.database.commit()   
            result=f"Changed the auto log channel to <#{autochannel.id}>"
            await MessageTemplates.server_archive_message(ctx,result)
    @archive_setup.command(name="updatenextauto", brief="change the next automatic time.")
    @app_commands.describe(newtime= "Minutes from now.")
    async def taskautochange(self, ctx,newtime:int):
        """set a new time for the next automatic task."""
        bot=ctx.bot
        guild=ctx.guild
        task_name="COMPILE"
        if not(serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(ctx,"You don't have permission to use this command..")
            return False
        
        old=TCGuildTask.get(guild.id, task_name)
        if old:
            old.change_next_run(self.bot,datetime.now()+timedelta(minutes=newtime))
            result=f"Time has changed to newtime."
            await MessageTemplates.server_archive_message(ctx,result)
        else:
            await MessageTemplates.server_archive_message(ctx,"I can't find the guild task.")
    
    @archive_setup.command(name="disable_auto", brief="stop automatically archiving")
    async def task_remove(self, ctx):
        """remove an automatic task."""
        bot=ctx.bot
        guild=ctx.guild
        task_name="COMPILE"
        if not(serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(ctx,"You don't have permission to use this command..")
            return False
        message=await ctx.send("Target Message.")
        myurl=message.jump_url
        new=TCGuildTask.remove_guild_task(guild.id, task_name)
        
        result=f"the auto archive has been disabled."
        await MessageTemplates.server_archive_message(ctx,result)
    
    @archive_setup.command(name="autosetup_archive", brief="automatically add a archive channel in invoked category with historian role.  ")
    async def createArchiveChannel(self, ctx):  # Add ignore.
        '''Want to set up a new archive channel automatically?  Use this command and a new archive channel will be created in this server with a historian role that only allows the bot user from posting inside the channel.

        The bot must have **Manage Channels** and **Manage Roles** to use this command.
        '''

        bot = ctx.bot
        auth = ctx.message.author
        channel:discord.TextChannel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        if not(serverOwner(ctx) or serverAdmin(ctx)):
            result="You lack permissions to use this command."
            await MessageTemplates.server_archive_message(ctx,result)
            return
        
        my_permissions= guild.me.guild_permissions

        permission_check_string=""
        if not my_permissions.manage_roles:
            permission_check_string="I don't have the **'Manage Roles'** permission needed to create a 'Historian' role."
        if not my_permissions.manage_channels:
            permission_check_string="I can't make you an archive channel without the **'Manage Channels'** permission."
        if not my_permissions.manage_roles and not my_permissions.manage_channels:
            permission_check_string="To create an archive channel and set the proper permissions, I need the **'Manage Roles'** and **'Manage Channels'** permissions."
        
        if permission_check_string:
            result=f"{permission_check_string}\n  Please update my permissions in Server Settings.  \n*You may remove the permissions after this command finishes.*"
            await MessageTemplates.server_archive_message(ctx,result)
            return

        profile=ServerArchiveProfile.get_or_new(guildid)

        #Check if history channel already exists.
        if profile.history_channel_id:
            if guild.get_channel(profile.history_channel_id):
                result="You already have a set archive channel, no reason for me to make a new one."
                await MessageTemplates.server_archive_message(ctx,result)
                return



        # create Historian role and give it to bot
        historian_role = discord.utils.get(guild.roles, name="Historian")
        if historian_role is None:
            historian_role = await guild.create_role(name="Historian")

        if historian_role not in guild.me.roles:
            await guild.me.add_roles(historian_role)

        # create new channel and set permissions for Historian role
        category = channel.category
        channel_name = "history-archive"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=False), # disallow sending messages for @everyone role
            historian_role: discord.PermissionOverwrite(send_messages=True) # allow sending messages for Historian role
        }
        new_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

        profile.add_or_update(guildid,history_channel_id=new_channel.id)

        bot.database.commit()
        
        await MessageTemplates.server_archive_message(ctx,"Created and set a new Archive channel for this server.")

    @archive_setup.command(
        name="add_ignore_channels",
        brief="Add mentioned channels to this server's ignore list. Ignored channels will not be archived."
    )
    async def addToIgnoredChannels(self, ctx):  # Add ignore.
        '''
        Add mentioned channels to this server's ignore list. Ignored channels will not be archived.
        '''
        bot = ctx.bot
        thismessage=ctx.message
        auth = ctx.message.author
        channel = ctx.message.channel
        def check(m):
            return m.author==auth and m.channel == channel
        if ctx.interaction:
            await ctx.send(f"Due to app command limitations, please specify all the channels you want to ignore in another message below, you have {get_time_since_delta(timedelta(minutes=15))}.")
            try:
                msg = await bot.wait_for('message', timeout=60.0*15, check=check)
                thismessage=msg
            except asyncio.TimeoutError:
                await ctx.send('You took way too long.')
                return

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
        brief="emoves channels from this server's ignore list."
    )
    async def removeFromIgnoredChannels(self, ctx):  # Add card.
        '''
        Removes channels from this server's ignore list. These channels will be archived.
        '''
        bot = ctx.bot
        thismessage=ctx.message
        auth = ctx.message.author
        channel = ctx.message.channel
        def check(m):
            return m.author==auth and m.channel == channel
        if ctx.interaction:
            await ctx.send(f"Due to app command limitations, please specify all the channels you want to stop ignoring in another message below, you have {get_time_since_delta(timedelta(minutes=15))}.")
            try:
                msg = await bot.wait_for('message', timeout=60.0*15, check=check)
                thismessage=msg
            except asyncio.TimeoutError:
                await ctx.send('You took way too long.')
                return

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
        By default, it only indexes bot/webhook messages.
        """
        bot = ctx.bot
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
            await ctx.send("Set a history channel first.")
            return False

        last_time=profile.last_archive_time
        await ctx.send("timestamp:{}".format(last_time.timestamp()))




        
    async def edit_embed_and_neighbors(self, target):
        '''
        This code checks if the target ChannelSep object has a 
        posted_url attribute, and then edits it's 
        
        '''
        async def edit_if_needed(target):
            if target:
                message=await urltomessage(target.posted_url,self.bot, partial=True)
                
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

    @commands.hybrid_command(
        name="compile_archive",
        brief="start archiving the server.  Will only archive messages sent by bots.",
        extras={"guildtask":['rp_history']})
    async def compileArchiveChannel(self, ctx):
        """Compile all messages into archive channel.  This can be invoked with options.
            +`full` - get the full history of this server
            +`update` -only update the current archive channel.  DEFAULT.

            +`ws` - compile only webhooks/BOTS.  DEFAULT.
            +`user` - complile only users
            +`both` -compile both
             
        """
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        guild:discord.Guild=channel.guild
        if guild==None:
            await ctx.send("This command will only work inside a guild.")
            return
        guildid=guild.id

        #options.
        update=True
        indexbot=True
        user=False
        scope='ws'
        archive_from="server"

        timebetweenmess=2.5
        characterdelay=0.05


        profile=ServerArchiveProfile.get_or_new(guildid)
        
        #for arg in args:
            #if arg == 'full':   update=False
            #if arg == 'update': update=True
        if scope == 'ws':      indexbot,user=True,False
        if scope == 'user':   indexbot,user=False, True
        if scope == 'both':   indexbot,user=True,True
        #await channel.send(profile.history_channel_id)
        if profile.history_channel_id == 0:
            await MessageTemplates.get_server_archive_embed(ctx,"Set a history channel first.")
            return False
        archive_channel=guild.get_channel(profile.history_channel_id)
        if archive_channel==None:
            await MessageTemplates.get_server_archive_embed(ctx,"I can't seem to access the history channel, it's gone!")
            return False

        #Make sure all permissions are there.
        missing_permissions = []
        passok, statusmessage = check_channel(archive_channel)

        if not passok:
            await MessageTemplates.server_archive_message(ctx,statusmessage)
            return


        m=await ctx.send("Initial check OK!")
        dynamicwait=False
        game=discord.Game("{}".format('archiving do not shut down...'))
        await bot.change_presence(activity=game)
        await m.edit(content="Collecting server history...")

        totalcharlen=0
        if archive_from=="server":
           messages, totalcharlen=await collect_server_history(ctx,update,indexbot,user)
        

        await  m.edit(content="Grouping into separators, this may take a while.")

        lastgroup=profile.last_group_num
        ts,group_id=await do_group(guildid,profile.last_group_num, ctx=ctx)
        fullcount=ts
        profile.update(last_group_num=group_id)
        remaining_time_float= fullcount* timebetweenmess
        print(lastgroup,group_id)
        if dynamicwait:
            remaining_time_float+=(totalcharlen*characterdelay)
        await m.edit(content=f"Posting! This is going to take about...{seconds_to_time_string(int(remaining_time_float))}")

        

        needed=ChannelSep.get_posted_but_incomplete(guildid)
        grouped=ChannelSep.get_unposted_separators(guildid)
        if needed:   grouped.insert(0,needed)
        length=len(grouped)
        for e,sep in enumerate(grouped):
            if not sep.posted_url:
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

                webhookmessagesent=await web.postWebhookMessageProxy(archive_channel, message_content=c, display_username=au, avatar_url=av, embed=amess.get_embed(), file=files)
                if webhookmessagesent:
                    amess.update(posted_url=webhookmessagesent.jump_url)
                    
                if dynamicwait:
                    chars=len(c)
                    await asyncio.sleep(characterdelay*chars)
                    await asyncio.sleep(timebetweenmess)
                    remaining_time_float=remaining_time_float-(timebetweenmess+characterdelay*chars)
                else:
                    await asyncio.sleep(timebetweenmess)
                    remaining_time_float=remaining_time_float-(timebetweenmess)
            sep.update(all_ok=True)
            self.bot.database.commit()
            game=discord.Game(f"Currently on {e+1}/{length}.\n  This is going to take about...{seconds_to_time_string(int(remaining_time_float))}")
            await bot.change_presence(activity=game)

        await asyncio.sleep(2)
        game=discord.Game("{}".format('clear'))
        await bot.change_presence(activity=game)
        channel=ctx.channel
        print(channel.name, channel.id)

        await MessageTemplates.server_archive_message(channel,f'Archive operation completed at <t:{int(datetime.now().timestamp())}:f>')
        await m.delete()
        
        


    @commands.command( extras={"guildtask":['rp_history']})
    async def makeCalendar(self, ctx):
        """Create a calendar of all archived messages with dates in this channel."""
        bot = ctx.bot
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id

        profile=ServerArchiveProfile.get_or_new(guildid)
        

        if profile.history_channel_id == 0:
            await MessageTemplates.get_server_archive_embed(ctx,"Set a history channel first.")
            return False
        if channel.id==profile.history_channel_id:
            return False
        #archive_channel=guild.get_channel(profile.history_channel_id)

        async def calendarMake(separator_messages, lastday=None, this_dates=["█","█","█","█","█","█","█"], current_calendar_embed_object=None, weeknumber=0):
            ##This code is old.
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

            print("Current Calendar Embed")

            for day in daystarts:
                date,url,mcount=day["date"],day["url"],day["mcount"]
                sepcount=day["sepcount"]
                if current_calendar_embed_object==None:
                    current_calendar_embed_object=discord.Embed(title=date.strftime("%B %Y"), colour=discord.Colour(randint(0,0xffffff)))
                if lastday != None:
                    if not same_week(lastday, date):
                        current_calendar_embed_object.add_field(name="Week {}".format(weeknumber), value="\n".join(this_dates), inline=True)
                        this_dates=["█","█","█","█","█","█","█"]
                        weeknumber=weeknumber+1
                    if not same_month(lastday, date):
                        await web.postWebhookMessageProxy(channel, message_content="_ _", display_username="DateMaster", avatar_url=bot.user.avatar.url, embed=[current_calendar_embed_object])
                        current_calendar_embed_object=discord.Embed(title=date.strftime("%B %Y"), colour=discord.Colour(randint(0,0xffffff)))
                        weeknumber=0
                else:
                    current_calendar_embed_object=discord.Embed(title=date.strftime("%B %Y"), colour=discord.Colour(randint(0,0xffffff)))
                strday=date.strftime("%m-%d-%Y")
                this_dates[date.weekday()]="[{}]({})-{}".format(strday, url, mcount)
                lastday=date
            current_calendar_embed_object.add_field(name="Week {}".format(weeknumber), value="\n".join(this_dates), inline=True)
            await web.postWebhookMessageProxy(channel, message_content="_ _", display_username="DateMaster", avatar_url=bot.user.avatar.url, embed=[current_calendar_embed_object])

        await calendarMake(ChannelSep.get_all_separators(guildid))
        



async def setup(bot):
    await bot.add_cog(ServerRPArchive(bot))



async def teardown(bot):
    await bot.remove_cog('ServerRPArchive')
