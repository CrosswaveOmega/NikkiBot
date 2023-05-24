import discord
from discord.ext import commands, tasks
from .MessageTemplates_EXT import MessageTemplatesMusic

async def connection_check(interaction: discord.Interaction,ctx:commands.Context, mode:int=3)->bool:
    '''Check if the calling user is connected to a voice channel, 
        and check if the bot is not currently connected to their same voice channel.
        Return True if Either of these conditions are satisfied (and the command should not run),
        and False if they are both 
        '''
    if (mode==3 or mode==1):
        if isinstance(interaction.user.voice, type(None)) and (mode==3 or mode==1):
            await MessageTemplatesMusic.music_msg(ctx, "You aren't connected", "You are not connected to any Voice Channel, I can't do anything.")
            return True
    if (mode==3 or mode==2):
        if interaction.user.voice.channel != ctx.voice_client.channel and (mode==3 or mode==2):
            await MessageTemplatesMusic.music_msg(ctx, "Not connected", "I'm not connected to your **Voice Channel!**")
            return True
    return False
