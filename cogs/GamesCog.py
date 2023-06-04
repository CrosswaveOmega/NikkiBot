import gui
from typing import Any, Coroutine
import discord
import operator
import io
import json
import aiohttp
import asyncio
import csv
#import datetime
from datetime import datetime, timedelta

from queue import Queue

from discord.ext import commands, tasks
from discord.interactions import Interaction
from discord.utils import find
from discord import Webhook,ui

from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import serverAdmin, serverOwner, MessageTemplates
from utility.embed_paginator import pages_of_embeds
from bot import TC_Cog_Mixin, super_context_menu

class MenuButton(discord.ui.Button['MenuButton']):
        def __init__(self,*args, **kwargs):
            gui.gprint("init")
            super().__init__(**kwargs)
        async def callback(self, interaction):
            await self.view.confirm(interaction,self)
        async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
            await interaction.response.send_message(f'Error: {str(error)}', ephemeral=True)


class GameMenu(discord.ui.View):
    def __init__(self,em=False):
        super().__init__(timeout=None)
        self.my_menu={'fire':{'a':True,'b':True,'c':True},'special':True}
        self.chain=[]
        self.level=0
        buttons=['fire','special','exit']
        
        self.reload()

    async def caller(self,interaction):
        gui.gprint('Call')
        await interaction.responce.send_message(self.texinp.value)
    def reload(self):
        gui.gprint(self.chain)
        menu=self.my_menu
        for i in self.chain:  menu=menu[i]
        if menu==True: return 'end'
        self.clear_items()
        for b,l in menu.items():
            button=MenuButton(label=b,style=discord.ButtonStyle.primary,custom_id=b,row=1)
            self.add_item(button)
        button=MenuButton(label='back',style=discord.ButtonStyle.primary,custom_id='back',row=1)
        self.add_item(button)
        return 'done'
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        '''Make sure the my_poll dictionary is filled out, and return.'''
        gui.gprint("ok jrtr", button.custom_id)
        if button.custom_id=='back':
            if len(self.chain)>0:
                self.chain.pop()
        else: self.chain.append(button.custom_id)
        gui.gprint(self.chain)
        reload_status=self.reload()
        if reload_status=='end':
              await interaction.response.edit_message(content=str(self.chain),view=None)
              self.stop()
        else:  await interaction.response.edit_message(content=button.custom_id,view=self)
        

        
class Games(commands.Cog, TC_Cog_Mixin):
    """Commands for some games.  Eventually."""
    def __init__(self, bot):
        self.helptext=""
        self.bot=bot

    @app_commands.command(name="menu_test", description="Testing for a game menu.")
    async def menutest(self, interaction: discord.Interaction) -> None:
        ctx: commands.Context = await self.bot.get_context(interaction)
        await ctx.send(view=GameMenu())
    




async def setup(bot):
    await bot.add_cog(Games(bot))
