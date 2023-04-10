import discord
import operator
import csv
from discord.ext import commands, tasks

from discord import Webhook
from pathlib import Path
import json



#I need to redo the permission system.  
def serverOwner(ctx):
    user=ctx.message.author
    guild=ctx.message.channel.guild
    guild_owner=guild.owner_id
    if (user.id==guild_owner):
        return True
    return False

def serverAdmin(ctx):
    user=ctx.message.author
    perm=user.guild_permissions
    if (perm.administrator or perm.manage_messages):
        return True
    return False
