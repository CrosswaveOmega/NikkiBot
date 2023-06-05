# Nikki Bot

Nikki Bot is a personal multipurpose, experimental Discord bot written using the discord.py library.

Support Server: https://discord.gg/zrHrkqkD5a
Invite Link: https://discord.com/api/oauth2/authorize?client_id=1069780327502975006&permissions=40581639556672&scope=applications.commands%20bot

## Features

1. **Server archive system**: This feature is designed for roleplaying servers. It condenses recent roleplay messages into a chronologically ordered channel called the Archive Channel, grouping them into clusters based on the original channel names and timestamps. This makes it easier for users to find relevant messages without cluttering the main chat channels.

2. **Advanced dice roll calculator**: This feature is a specialized calculator that supports nested operations. It can be used for tabletop roleplaying games, board games, or any other activity that requires rolling dice. The calculator is customizable and can handle complex formulas.

3. **TCGuildTask system**: This feature allows for the creation of specialized server unique tasks that execute at regular intervals, such as every day/week/month at specific times, on specific weekdays, and so on. 
Data for each task is represented by the entries within a SQLAlchemy table with the server ID, the name of the task, the interval, a channel ID for the 'autolog' channel, and the datetime for the next run. 
The tasks can be customized by adding coroutines to the Guild_Task_Functions class, within the bot's Cogs. 

4. **Music Player**: A Music Player that can play songs in voice channnels.  

5. **Server Polling System**: A work in progress feature that allows users to create and respond to global and server specific polls.

6. **Optional GUI Panel**: A Tkinter GUI Window displays basic status about the running bot within a desktop window.

7. **More features to come!**: The bot is constantly being updated and new features will be added as they become available.


## Current Requirements
Python 3.11 or higher!
- discord.py
- SQLAlchemy
- python-dateutil
- ~~youtube_dl~~ yt_dlp

## Technical Features

- Nikki is designed to be as modular as possible, with every single extension in a self contained file.
- Experimental autosync system which only syncs app command trees if it detects a difference between dictionary representations of the app command tree.

## How to use the TCGuildTask system

1. To use the TCGuildTask system, the task function needs to be defined and added to the Guild_Task_Functions class.  This is done with the `Guild_Task_Functions.add_task_function` method within a `commands.Cog` init method, passing in a unique name and a coroutine defined within the Cog.  This coroutine should take a single argument, a discord.TextMessage object called source_message that is passed to the `execute_task_function` method.

```
def __init__(self, bot:TCBot):
   self.bot=bot
   ...

   Guild_Task_Functions.add_task_function("TASKNAMEHERE",self.gtaskcoroutine)

def cog_unload(self):
   Guild_Task_Functions.remove_task_function("TASKNAMEHERE")


async def gtaskcoroutine(self, source_message:discord.TextMessage):
   #Insert code here.
```
2. These tasks won't run until an admin/moderator for the guild uses a corresponding command that will add an entry to the TCGuildTask table, specifying that they want that task to run within their server at a regular time interval.  The admin/moderator must set specify an **autolog** channel with this command, to both log whenever the bot runs the task (and if there are any errors), and so that the bot can generate a context message in case the guild task runs any of the bot's commands.

3. Upon creation of a TCGuildTask entry, a TCTask object will be added to the bot's TCTaskManager, and will run once the current datetime reaches the datetime specified in the next_run property.

4. The task will run at the specified interval, creating a context message within the server's autolog channel. After the task finishes executing, the next run attribute is calculated based on the task's time interval attribute, and saved to the TCGuildTask table.

##
