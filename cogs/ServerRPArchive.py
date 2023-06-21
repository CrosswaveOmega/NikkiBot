import gui
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

from utility import serverOwner, serverAdmin, seconds_to_time_string, get_time_since_delta, formatutil
from utility import WebhookMessageWrapper as web, urltomessage, ConfirmView, RRuleView
from bot import TCBot, TCGuildTask, Guild_Task_Functions, StatusEditMessage, TC_Cog_Mixin
from random import randint
from discord.ext import commands, tasks

from dateutil.rrule import rrule,rrulestr, WEEKLY, SU, MINUTELY, HOURLY

from discord import Webhook



from discord import app_commands
from discord.app_commands import Choice


from database import ServerArchiveProfile
from .ArchiveSub import do_group
from .ArchiveSub import (
  collect_server_history,
  check_channel,
  ArchiveContext,
  collect_server_history_lazy,
  setup_lazy_grab,
  lazy_archive,
  LazyContext

) 
from .ArchiveSub import ChannelSep, ArchivedRPMessage, MessageTemplates, HistoryMakers, ChannelArchiveStatus
from collections import defaultdict
class ToChoice(commands.Converter):
    async def convert(self, ctx, argument):
        if not ctx.interaction:
            print(type(argument))
            if type(argument)==str:
                choice=Choice(name="fallback",value=argument)
                return choice
        else:
            return argument

class ServerRPArchive(commands.Cog, TC_Cog_Mixin):
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
        self.guild_cache= defaultdict(int)
        self.guild_db_cache= defaultdict(lambda: None)

        Guild_Task_Functions.add_task_function("COMPILE",self.gtask_compile)
        
        Guild_Task_Functions.add_task_function("LAZYARCHIVE",self.gtask_lazy)

    def cog_unload(self):
        #Remove the task function.
        Guild_Task_Functions.remove_task_function("COMPILE")
        pass
    
    def server_profile_field_ext(self,guild:discord.Guild):
        profile=ServerArchiveProfile.get(guild.id)
        if not profile:  return None
        last_date=aid=""
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
            if autoentry:
                res=autoentry.get_status_desc()
                if res:      value+=res
            field={"name":"Server RP Archive",'value':value}
            return field
        return None




    async def gtask_lazy(self, source_message=None):
        '''This is the Guild task for the Lazy Archive Mode, intended for massive servers.'''
        if not source_message: return None
        context=await self.bot.get_context(source_message)
        try:
            result=await lazy_archive(self,context)
            if result==False:
                gui.gprint("Done.")
                TCGuildTask.get(context.guild.id, "LAZYARCHIVE").remove_after=True
            await source_message.delete()
        except Exception as e:
            er=MessageTemplates.get_error_embed(title=f"Error with AUTO",description=f"{str(e)}")
            await source_message.channel.send(embed=er)
            TCGuildTask.get(context.guild.id, "LAZYARCHIVE").remove_after=True
            raise e
        

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
                gui.gprint(user.name)
                profile.add_user_to_list(user.id)
        self.guild_db_cache[str(ctx.guild.id)]=profile
        self.bot.database.commit()

    @commands.hybrid_group(fallback="view")
    @app_commands.default_permissions(manage_messages=True,manage_channels=True)
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True,manage_channels=True)
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
        gui.gprint(profile)
        passok, statusmessage = check_channel(chanment)
        if not passok:
            await MessageTemplates.server_archive_message(ctx,statusmessage)
            return
        if profile.history_channel_id:
            choice=await MessageTemplates.confirm(ctx,"Are you sure you want to change your archive channel?")
            if not choice:
                await MessageTemplates.server_archive_message(ctx,"The Server Archive Channel has been set.")
        newchan_id=chanment.id
        profile.add_or_update(guildid,history_channel_id=newchan_id)
        self.guild_db_cache[str(ctx.guild.id)]=profile
        bot.database.commit()
        
        await MessageTemplates.server_archive_message(ctx,"The Server Archive Channel has been set.")

    
    @archive_setup.command(name="enable_auto", brief="automatically archive the server every sunday at 4pm.")
    @app_commands.describe(autochannel= "a channel where the command will run.  not same thing as the archive_channel!")
    async def enable_auto(self, ctx,autochannel:discord.TextChannel):
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
            start_date = datetime(2023, 1, 1, 15, 0)
            robj= rrule(
                freq=WEEKLY,
                byweekday=SU,
                dtstart=start_date
            )

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
    async def updatenextauto(self, ctx,newtime:int):
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
    @archive_setup.command(name="change_auto_interval", brief="change how often I archive the server.")
    async def change_auto_interval(self, ctx):
        """set a new time for the next automatic task."""
        bot=ctx.bot
        guild=ctx.guild
        task_name="COMPILE"
        if not(serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(ctx,"You don't have permission to use this command..")
            return False
        
        old=TCGuildTask.get(guild.id, task_name)
        if old:
            view = RRuleView(ctx.author)
            message=await ctx.send("Understood!  Please use the view below to change the recurrence rules for archiving.\n"+\
                                   "Think of it like setting up a repeating event on your iPhone/Android.", view=view,  ephemeral=True)
            await asyncio.sleep(2)
            await view.wait()
            if view.value=='TIMEOUT':
                await ctx.send("Sorry, you hit a timeout, try again later.")
            elif view.value:
                await ctx.send(f"`{str(view.value)}`")
                old.change_rrule(self.bot,view.value)
                desc,sent=formatutil.explain_rrule(view.value)
                result=f"I've changed the recurrence settings! \n {sent}"
                await MessageTemplates.server_archive_message(ctx,result)
            else:
                await ctx.send("I see.  I'll stop.")
            #await message.delete()

        else:
            await MessageTemplates.server_archive_message(ctx,"I can't find the guild task.")
    
    @archive_setup.command(name="disable_auto", brief="stop automatically archiving the server")
    async def disable_auto(self, ctx):
        """remove an automatic task."""
        bot=ctx.bot
        guild=ctx.guild
        task_name="COMPILE"
        if not(serverOwner(ctx) or serverAdmin(ctx)):
            await MessageTemplates.server_archive_message(ctx,"You don't have permission to use this command.")
            return False
        message=await ctx.send("Target Message.")
        myurl=message.jump_url
        new=TCGuildTask.remove_guild_task(guild.id, task_name)
        
        result=f"the auto archive has been disabled."
        await MessageTemplates.server_archive_message(ctx,result)
    
    @archive_setup.command(name="autosetup_archive", brief="the bot will create a new archive channel.")
    @app_commands.checks.bot_has_permissions(manage_channels=True,manage_roles=True)
    @commands.bot_has_guild_permissions(manage_channels=True,manage_roles=True)
    async def autosetup_archive(self, ctx):  # Add ignore.
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
        self.guild_db_cache[str(ctx.guild.id)]=profile
        bot.database.commit()
        
        await MessageTemplates.server_archive_message(ctx,"Created and set a new Archive channel for this server.")

    @archive_setup.command(
        name="add_ignore_channels",
        brief="Add mentioned channels to this server's ignore list. Ignored channels will not be archived."
    )
    async def add_ignore_channels(self, ctx):  # Add ignore.
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
            await ctx.send(f"Due to app command limitations, please specify all the channels you want to ignore in another message below, you have {formatutil.get_time_since_delta(timedelta(minutes=15))}.")
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
        self.guild_db_cache[str(ctx.guild.id)]=profile
        await MessageTemplates.server_archive_message(ctx,"Added channels to my ignore list.  Any messages in these channels will be ignored while archiving.")

        


    @archive_setup.command(
        
        name="remove_ignore_channels",
        brief="removes channels from this server's ignore list."
    )
    async def remove_ignore_channels(self, ctx):  
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
            await ctx.send(f"Due to app command limitations, please specify all the channels you want to stop ignoring in another message below, you have {formatutil.get_time_since_delta(timedelta(minutes=15))}.")
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
        self.guild_db_cache[str(ctx.guild.id)]=profile
        self.bot.database.commit()
        await MessageTemplates.server_archive_message(ctx,"Removed channels from my ignore list.  Any messages in these channels will no longer be ignored while archiving.")
    
    
    @archive_setup.command(name="set_scope", description="Configure the archive scope, the bot will archive messages only if the authors are in this scope.")
    @app_commands.choices(
    scope=[ # param name
        Choice(name="Only Archive Bot Messages", value="ws"),
        Choice(name="Only Archive User Messages", value="user"),
        Choice(name="Archive All Messages", value="both")
    ]
    )
    async def set_scope(self, ctx,scope: ToChoice):  
        if ctx.guild:
            scopes={
                'ws':"Bots and Webhook Messages Only",
                'user':"User Messages Only",
                'both': "Every message, reguardless of sender"
            }
            print(scope)
            profile=ServerArchiveProfile.get_or_new( ctx.guild.id)
            oldscope=profile.archive_scope
            if not oldscope: oldscope='ws'
            print(oldscope)
            if scope not in ['ws','user','both']:
                await ctx.send(f"The specified scope {scope} is invalid.")
            steps=['# Warning! \n  Changing the archive scope can cause issues if you already have messages within my log!'+\
                   "\nAre you sure about this?",
                    f"You are?  Alright, so just to be clear, you want me \nto begin archiving **{scopes[scope]}**"+\
                    f"instead of archiving **{scopes[oldscope]}.**\nIs that correct?",
                    f"I need one final confirmation before I change the setting.  \n You are sure you want to change the archive scope?"
            ]
            for r in steps:
                confirm=ConfirmView(user=ctx.author)
                mes=await ctx.send(r,view=confirm)
                await confirm.wait()
                if not confirm.value:
                    await MessageTemplates.server_archive_message(ctx,f"Very well, scope changed aborted.", ephemeral=True)
                confirm.clear_items()
                await mes.edit(view=confirm)
            
            profile.update(archive_scope=scope)
            self.guild_db_cache[str(ctx.guild.id)]=profile
            await MessageTemplates.server_archive_message(ctx,f"Ok then, I've changed the archive scope.", ephemeral=True)
        else:
            await ctx.send("guild only.")
    @archive_setup.command(name="set_active_collect", description="Nikki can store rp messages in her database when they are sent, use this to enable that setting.")
    @app_commands.describe(
            mode="True if Nikki should store RP messages in her database when recieved, False otherwise.")
    async def set_active(self, ctx, mode:bool=False):  
        if ctx.guild:
            
            profile=ServerArchiveProfile.get_or_new( ctx.guild.id)
            oldscope=profile.archive_dynamic
            if oldscope==mode:
                await ctx.send("This is the same as my current setting.")
            steps=["# Warning! \n  **Before** you use this command, please make sure you've used my `add_ignore_channels` command on all channels you don't want me reposting into my log!"\
                   +"\n Did you check this?"
            ]
            for r in steps:
                confirm=ConfirmView(user=ctx.author)
                mes=await ctx.send(r,view=confirm)
                await confirm.wait()
                if not confirm.value:
                    await MessageTemplates.server_archive_message(ctx,f"Very well, scope changed aborted.", ephemeral=True)
                confirm.clear_items()
                await mes.edit(view=confirm)
            
            profile.update(archive_dynamic=mode)
            self.guild_db_cache[str(ctx.guild.id)]=profile
            if mode==True:
                self.guild_cache[str(ctx.guild.id)]=2
            else:
                self.guild_cache[str(ctx.guild.id)]=1
            await MessageTemplates.server_archive_message(ctx,f"Alright, I've changed my active gather mode.", ephemeral=True)
        else:
            await ctx.send("guild only.")
    
    @archive_setup.command(name="postcheck", description="Check number of stored archived messages that where posted.")
    async def postcheck(self, ctx):  
        if ctx.guild:
            
            mess2=ArchivedRPMessage.get_archived_rp_messages_with_null_posted_url(ctx.guild.id)
            mess=ArchivedRPMessage.get_archived_rp_messages_without_null_posted_url(ctx.guild.id)
            await MessageTemplates.server_archive_message(ctx,f"About {len(mess)} messages are posted, and {len(mess2)} messages are not posted.", ephemeral=True)
        else:
            await ctx.send("guild only.")
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    @commands.command(name="lazymode", description="For big, unarchived servers.")
    async def setup_lazy_archive(self, ctx,autochannel:discord.TextChannel, *args):  
        if ctx.guild:

            bot=ctx.bot
            guild=ctx.guild
            profile=ServerArchiveProfile.get_or_new(guild.id)
            if profile.history_channel_id == 0:
                await MessageTemplates.get_server_archive_embed(ctx,"Set a history channel first.")
                return False
            archive_channel=guild.get_channel(profile.history_channel_id)
            if archive_channel==None:
                await ctx.send("I can't seem to access the history channel, it's gone!")
                return False
            if profile.last_archive_time!=None:
                await MessageTemplates.server_archive_message(ctx,"There's no reason for you to use lazy mode, this server is already archived.")
                confirm=ConfirmView(user=ctx.author)
                mes=await ctx.send("Continue anyways?",view=confirm)
                await confirm.wait()
                if not confirm.value:
                    return False
            passok, statusmessage = check_channel(archive_channel)

            if not passok:
                await MessageTemplates.server_archive_message(ctx,statusmessage)
                return  
            if not(serverOwner(ctx) or serverAdmin(ctx)):
                await MessageTemplates.server_archive_message(ctx,"You do not have permission to use this command.")
                return False
            if LazyContext.get(guild.id)!=None:
                LazyContext.remove(guild.id)
                #await MessageTemplates.server_archive_message(ctx,"There already is a running lazy archive.")
                #return False
            confirm=ConfirmView(user=ctx.author)
            mes=await ctx.send("Lazy archive mode WILL take a long time to finish, please make sure you set all your parameters.",view=confirm)
            await confirm.wait()
            if confirm.value:
                await mes.delete()
                task_name="LAZYARCHIVE"
                message=await autochannel.send(f"**ATTEMPTING SET UP OF AUTO COMMAND {task_name}**")
                myurl=message.jump_url
                start_date = datetime(2023, 1, 1, 15, 0)
                robj= rrule(
                    freq=HOURLY,
                    interval=1,
                    dtstart=start_date
                )


                await setup_lazy_grab(ctx)
                totaltime=ChannelArchiveStatus.get_total_unarchived_time(guild.id)
                
                lz=LazyContext.create(guild.id)
                if 'nocollect' in args:
                    lz.collected=True
                    lz.message_count=ArchivedRPMessage.count_all(guild.id)
                result=f"I've set up the lazy archive system for <#{autochannel.id}>!  You've got a combined {totaltime}(this is not how long this will take.) worth of messages to be compiled."
                new=TCGuildTask.add_guild_task(guild.id, task_name, message, robj)
                new.to_task(bot)
                bot.database.commit()
                await MessageTemplates.server_archive_message(ctx,result)
            else:
                await mes.delete()
        else:
            await ctx.send("guild only.")

    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True,manage_messages=True)
    @commands.command(name="reset_archive", description="ADMIN ONLY: WILL RESET THE ARCHIVE GROUPING.")
    async def archive_reset(self, ctx):  
        if ctx.guild:
            
            profile=ServerArchiveProfile.get_or_new(ctx.guild.id)
            if profile.history_channel_id == 0:
                await MessageTemplates.get_server_archive_embed(ctx,"Set a history channel first.")
                return False
            if not(serverOwner(ctx) or serverAdmin(ctx)):
                await MessageTemplates.server_archive_message(ctx,"You do not have permission to use this command.")
                return False
            confirm=ConfirmView(user=ctx.author)
            mes=await ctx.send("Are you sure about this?",view=confirm)
            await confirm.wait()
            if confirm.value:
                await mes.delete()
                ChannelSep.delete_channel_seps_by_server_id(ctx.guild.id)
                ArchivedRPMessage.reset_channelsep_data(ctx.guild.id)
                profile.update(last_group_num=0)
                confirm2=ConfirmView(user=ctx.author)
                mes=await ctx.send("I can delete the current history channel if you want to start fresh, is that ok?",view=confirm2)
                await confirm2.wait()
                if confirm2.value:
                    archive_channel=ctx.guild.get_channel(profile.history_channel_id)
                    cloned=await archive_channel.clone()
                    profile.update(history_channel_id=cloned.id)
                    await archive_channel.delete()
                await mes.delete()

                self.bot.database.commit()
                mess2=ArchivedRPMessage.get_archived_rp_messages_with_null_posted_url(ctx.guild.id)
                mess=ArchivedRPMessage.get_archived_rp_messages_without_null_posted_url(ctx.guild.id)
                await MessageTemplates.server_archive_message(ctx,
                    f"I've reset the grouping data for this server.  When you run another compile_archive, **everything in the archive_channel will be reposted.**")
                
            else:
                await mes.delete()
        else:
            await ctx.send("guild only.")


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


    @commands.command()
    async def setlastfirsttimestamp(self, ctx, time:int):
        """Set the timestamp to begin archiving at.
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

        if not(serverOwner(ctx) or serverAdmin(ctx)):  #Permission Check.
            return False


        profile=ServerArchiveProfile.get_or_new(guildid)


        if profile.history_channel_id == 0:
            await ctx.send("Set a history channel first.")
            return False

        profile.last_archive_time=datetime.fromtimestamp(time)
        self.bot.database.commit()
        await ctx.send("timestamp:{}".format(profile.last_archive_time.timestamp()))



        
    async def edit_embed_and_neighbors(self, target:ChannelSep):
        '''
        This code checks if the target ChannelSep object has a 
        posted_url attribute, and then edits it's neighbors.
        
        '''
        async def edit_if_needed(target):
            if target:
                message=await urltomessage(target.posted_url,self.bot)
                
                emb,lc=target.create_embed()
                gui.gprint(lc)
                target.update(neighbor_count=lc)
                await message.edit(embeds=[emb])
        gui.gprint(target, target.posted_url)
        if target.posted_url:
            iL=target.get_neighbor(False,False,False)
            cL=target.get_neighbor(True,False,False)
            gui.gprint(iL,cL,target)

            await edit_if_needed(iL)
            await edit_if_needed(cL)
            gui.gprint(f"New posted_url value for ChannelSep")

    #####################################FOR ACTIVE MODE##################################
    def guild_check(self,guildid):
        '''Check if a guild is in the guild cache.'''
        if self.guild_cache[str(guildid)]==0:
            profile=ServerArchiveProfile.get(guildid)
            if not profile: 
                print('unset')
                self.guild_cache[str(guildid)]=1
                return 1
            if profile.archive_dynamic==True:
                print("Set")
                self.guild_cache[str(guildid)]=2
            else:
                self.guild_cache[str(guildid)]=1
        return self.guild_cache[str(guildid)]
    @commands.Cog.listener()
    async def on_message(self,message:discord.Message):
        
        if not message.guild: return
        guildid=message.guild.id

        if self.guild_check(guildid)==2:
            profile= self.guild_db_cache[str(guildid)]
            if not profile: 
                profile=profile=ServerArchiveProfile.get(guildid)
                self.guild_db_cache[str(guildid)]=profile
            
            actx=ArchiveContext(self.bot,profile=profile)
            if not actx.evaluate_add(message):
                gui.gprint("scope failure.")
                return
            if not actx.evaluate_channel(message):
                gui.gprint("channel failure.")
                return
            gui.gprint("Message added.")
            await HistoryMakers.get_history_message(message,active=True)

        pass
    @commands.Cog.listener()
    async def on_message_edit(self,before,message):
        if not message.guild: return
        guildid=message.guild.id

        if self.guild_check(guildid)==2:
            profile= self.guild_db_cache[str(guildid)]
            if not profile: 
                profile=profile=ServerArchiveProfile.get(guildid)
                self.guild_db_cache[str(guildid)]=profile
            if not profile: return
            if profile.archive_dynamic==True:
                m,e=ArchivedRPMessage.get(server_id=guildid,message_id=message.id)
                if m!=0:
                    e.update(content=message.clean_conent)
                    self.bot.database.commit()
        pass
    @commands.Cog.listener()
    async def on_message_delete(self,message):
        if not message.guild: return
        guildid=message.guild.id
        if self.guild_check(guildid)==2:
            profile= self.guild_db_cache[str(guildid)]
            if not profile: 
                profile=profile=ServerArchiveProfile.get(guildid)
                self.guild_db_cache[str(guildid)]=profile
            if not profile: return
            if profile.archive_dynamic==True:
                m,entry=ArchivedRPMessage.get(server_id=guildid,message_id=message.id)
                if m==2: #It was found, and is currently set to 'active'
                    session=self.bot.database.get_session()
                    session.delete(entry)
                    session.commit()
        pass
    
    @commands.command(
        name="archive_compile_lazy",
        brief="start archiving the server.  ",
        extras={"guildtask":['rp_history']})
    async def compileArchiveChannelLazy(self, ctx):
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

        timebetweenmess=2.0
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
        bot.add_act(str(ctx.guild.id),'archiving server...')
        
        await m.edit(content="Collecting server history...")

        totalcharlen=0
        new_last_time=0
        if archive_from=="server":
           messages, totalcharlen,new_last_time=await collect_server_history(ctx,update,indexbot,user)
        

        await  m.edit(content="Grouping into separators, this may take a while.")

        lastgroup=profile.last_group_num
        ts,group_id=await do_group(guildid,profile.last_group_num, ctx=ctx)
        fullcount=ts
        profile.update(last_group_num=group_id)
        remaining_time_float= fullcount* timebetweenmess
        gui.gprint(lastgroup,group_id)
        if dynamicwait:
            remaining_time_float+=(totalcharlen*characterdelay)

        gui.gprint('next')
        nogroup=ArchivedRPMessage.get_messages_without_group(guildid)
        needed=ChannelSep.get_posted_but_incomplete(guildid)
        grouped=ChannelSep.get_unposted_separators(guildid)
        all=ChannelSep.get_all_separators(guildid)
        unique_ids=ArchivedRPMessage.get_unique_chan_sep_ids(guildid)

        if needed:   
            grouped.insert(0,needed)
        if nogroup==None:
            nogroup=[]
        if needed==None: needed=[]

        
        gui.gprint(grouped,needed)
        await ctx.send(f'{len(nogroup)},  {len(needed)},{len(grouped)},{len(all)}, {len(unique_ids)}')
        unposted=len(ArchivedRPMessage.get_archived_rp_messages_with_null_posted_url(guildid))
        
        for group in grouped:
            group.channel_sep_id
            messages_get=group.get_messages()
            query2=ArchivedRPMessage.get_messages_in_group(guildid,group.channel_sep_id)
            await ctx.send(f"{len(messages_get)},{len(query2)}")
            unposted-=len(messages_get)
        await ctx.send(f"Remaining:{unposted}")
        

    @commands.hybrid_command(
        name="compile_archive",
        brief="start archiving the server.  Will only archive messages based on defined archive scope.",
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

        timebetweenmess=2.2
        characterdelay=0.05


        profile=ServerArchiveProfile.get_or_new(guildid)
        

        #await channel.send(profile.history_channel_id)
        if profile.history_channel_id == 0:
            await MessageTemplates.get_server_archive_embed(ctx,"Set a history channel first.")
            return False
        archive_channel=guild.get_channel(profile.history_channel_id)
        if archive_channel==None:
            await MessageTemplates.get_server_archive_embed(ctx,"I can't seem to access the history channel, it's gone!")
            return False

        
        passok, statusmessage = check_channel(archive_channel)

        if not passok:
            await MessageTemplates.server_archive_message(ctx,statusmessage)
            return

        m2=await ctx.send("archiving...")
        m=await ctx.channel.send("Initial check OK!")
        dynamicwait=False
        bot.add_act(str(ctx.guild.id)+"arch",'archiving server...')
        await m.edit(content="Collecting server history...")

        totalcharlen=0
        new_last_time=0
        if archive_from=="server":
           messages, totalcharlen,new_last_time=await collect_server_history(
               ctx,
               update=update
               )
        

        await  m.edit(content="Grouping into separators, this may take a while.")

        lastgroup=profile.last_group_num
        ts,group_id=await do_group(guildid,profile.last_group_num, ctx=ctx)

        fullcount=ts
        profile.update(last_group_num=group_id)
        
        gui.gprint(lastgroup,group_id)
        if dynamicwait:
            remaining_time_float+=(totalcharlen*characterdelay)

        gui.gprint('next')

        needed=ChannelSep.get_posted_but_incomplete(guildid)
        grouped=ChannelSep.get_unposted_separators(guildid)
        if needed:   
            grouped.insert(0,needed)
        length=len(grouped)
        gui.gprint(grouped,needed)
        message_total,total_time_for_cluster=0,0.0
        for sep in grouped: 
            message_total+=sep.message_count
        total_time_for_cluster=message_total*timebetweenmess
        #time between each delay.
        total_time_for_cluster+=(length*2)

        remaining_time_float= total_time_for_cluster

        await m.edit(content=f"It will take {seconds_to_time_string(int(remaining_time_float))} to post in the archive channel.")
        me=await ctx.channel.send(content=f"<a:LetWalk:1118184074239021209> This is going to take about...{seconds_to_time_string(int(remaining_time_float))}")
        mt=StatusEditMessage(me,ctx)
        gui.gprint(archive_channel.name)

        for e,sep in enumerate(grouped):
            #Start posting
            gui.gprint(e,sep)
            if not sep.posted_url:
                currjob="rem: {}".format(seconds_to_time_string(int(remaining_time_float)))
                emb,count=sep.create_embed()
                chansep=await archive_channel.send(embed=emb)
                sep.update(posted_url=chansep.jump_url)
                await self.edit_embed_and_neighbors(sep)
                self.bot.database.commit()
            messages=sep.get_messages()
            messagelength=len(messages)
            for index,amess in enumerate(messages):
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
                    await mt.editw(min_seconds=45,content=f"<a:LetWalk:1118184074239021209> Currently on {e+1}/{length}.\n index{index}/{messagelength} \n This is going to take about...{seconds_to_time_string(int(remaining_time_float))}")
            sep.update(all_ok=True)
            self.bot.database.commit()
            await asyncio.sleep(2)
            remaining_time_float-=2
            await mt.editw(min_seconds=30,content=f"<a:LetWalk:1118184074239021209> Currently on {e+1}/{length}.\n  This is going to take about...{seconds_to_time_string(int(remaining_time_float))}")
            #await edittime.invoke_if_time(content=f"Currently on {e+1}/{length}.\n  This is going to take about...{seconds_to_time_string(int(remaining_time_float))}")
            bot.add_act(str(ctx.guild.id)+"arch",f"Currently on {e+1}/{length}.\n  This is going to take about...{seconds_to_time_string(int(remaining_time_float))}")

        await asyncio.sleep(2)
        await me.delete()
        game=discord.Game("{}".format('clear'))
        await bot.change_presence(activity=game)

        bot.remove_act(str(ctx.guild.id)+"arch")
        channel=ctx.channel
        latest=ArchivedRPMessage.get_latest_archived_rp_message(ctx.guild.id)
        gui.gprint(discord.utils.utcnow(),latest.created_at, profile.last_archive_time,datetime.fromtimestamp(int(new_last_time)))
        profile.update(last_archive_time=latest.created_at)
        bot.database.commit()
        await m2.delete()
        await MessageTemplates.server_archive_message(channel,f'Archive operation completed at <t:{int(datetime.now().timestamp())}:f>')
        self.guild_db_cache[str(guildid)]=profile
        bot.database.commit()

        #await m.delete()
        
        


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
        archive_channel=guild.get_channel(profile.history_channel_id)
        if archive_channel==None:
            await MessageTemplates.get_server_archive_embed(ctx,"I can't seem to access the history channel, it's gone!")
            return False

        thread=discord.utils.get(archive_channel.threads, name="Message Calendar")
        if thread:
            await thread.delete()
        new_thread=await archive_channel.create_thread(name="Message Calendar", auto_archive_duration=10080, type=discord.ChannelType.public_thread )

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
                gui.gprint((lastdate-newdate.date()).days)
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

            gui.gprint("Current Calendar Embed")

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
                        await web.postWebhookMessageProxy(new_thread, message_content="_ _", display_username="DateMaster", avatar_url=bot.user.avatar.url, embed=[current_calendar_embed_object])
                        current_calendar_embed_object=discord.Embed(title=date.strftime("%B %Y"), colour=discord.Colour(randint(0,0xffffff)))
                        weeknumber=0
                else:
                    current_calendar_embed_object=discord.Embed(title=date.strftime("%B %Y"), colour=discord.Colour(randint(0,0xffffff)))
                strday=date.strftime("%m-%d-%Y")
                this_dates[date.weekday()]="[{}]({})-{}".format(strday, url, mcount)
                lastday=date
            current_calendar_embed_object.add_field(name="Week {}".format(weeknumber), value="\n".join(this_dates), inline=True)
            await web.postWebhookMessageProxy(new_thread, message_content="_ _", display_username="DateMaster", avatar_url=bot.user.avatar.url, embed=[current_calendar_embed_object])

        await calendarMake(ChannelSep.get_all_separators(guildid))
        



async def setup(bot):
    await bot.add_cog(ServerRPArchive(bot))



async def teardown(bot):
    await bot.remove_cog('ServerRPArchive')
