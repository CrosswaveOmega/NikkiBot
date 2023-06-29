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

7. **Dynamic Tag System**: Create, edit, and retrieve dynamic tags, with a javascript wrapper.

8. **PurGPT integration:** Can be integreated with the PurGPT API to access and utilize a number of AI Models, with a built in server/user limiting system to prevent api abuse.

9. **Natural Language Command Invocation:**  This bot is capable of invoking it's own Bot Commands through natural language, thanks to OpenAI Funciton calling and a special set of decorators.

10. **More features to come!**: The bot is constantly being updated and new features will be added as they become available.


## Current Requirements
Python 3.11 or higher!
- discord.py
- SQLAlchemy
- python-dateutil
- yt_dlp
- sqlitedict
- playwright
- JSPyBridge

## Technical Features
-
- Experimental autosync system which only syncs app command trees if it detects a difference between saved dictionary representations of the App Command Tree.
