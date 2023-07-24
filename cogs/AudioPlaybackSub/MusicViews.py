import discord

class WeekdayButton(discord.ui.Button):
    def __init__(self, myvalue=False,**kwargs):
        self.value = myvalue
        super().__init__(**kwargs)
        
        if self.value:
            self.style = discord.ButtonStyle.green
        else:
            self.style = discord.ButtonStyle.grey

    async def callback(self, interaction: discord.Interaction):
        self.value = not self.value
        if self.value:
            self.style = discord.ButtonStyle.green
            
            self.view.dtvals['days'].append(self.custom_id)
        else:
            self.style = discord.ButtonStyle.grey
            self.view.dtvals['days'].remove(self.custom_id)
        await interaction.response.edit_message(view=self.view, embed=self.view.emb())

class PlayerButtons(discord.ui.View):
    '''buttons for the audio player.'''
    def __init__(self, *, timeout=None, inter=None, callback=None):
        super().__init__(timeout=timeout)
        self.callbacker=callback
        self.inter=inter
        self.playlistviewmode=False
        self.pview=None
        self.setplaypause()
        self.changenextlast()

    def setplaypause(self):
        if  self.callbacker.player_condition=='play':
            self.playpause_button.emoji='⏸'
            self.playpause_button.label='pause'
        else:
            self.playpause_button.emoji='▶️'
            self.playpause_button.label='play'
    
    def changenextlast(self):
        if  self.playlistviewmode:
            self.backpage_button.emoji='⬅️'
            self.nextpage_button.emoji='➡️'
            self.backpage_button.label='last page'
            self.nextpage_button.label='next page'
        else:
            self.backpage_button.emoji=None
            self.nextpage_button.emoji=None
            self.backpage_button.label='_ _'
            self.nextpage_button.label='_ _'
    async def updateview(self,inter:discord.Interaction):
        self.setplaypause()
        self.changenextlast()
        await inter.edit_original_response(view=self)
    @discord.ui.button(emoji='⬅️',label="back",style=discord.ButtonStyle.blurple) # or .primary
    async def backpage_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        if self.pview:
            self.pview.update_display()
            await self.pview.playlistcallback(interaction,self,"back")
        else: await interaction.response.defer()
        #await self.callbacker.playlistcallback(interaction,self,"back")

    @discord.ui.button(emoji='⏮️',label="back",style=discord.ButtonStyle.blurple) # or .primary
    async def back_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer()#(content="back pressed",view=self)
        await self.callbacker.player_button_call(interaction,"back")
    @discord.ui.button(emoji='⏯',label="playpause",style=discord.ButtonStyle.blurple) # or .primary
    async def playpause_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer()#(content="Next pressed",view=self)
        await self.callbacker.player_button_call( interaction,button.label)
        await self.updateview(interaction)
    '''@discord.ui.button(emoji='▶️',label="play",style=discord.ButtonStyle.blurple) # or .primary
    async def play_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer()#(content="Next pressed",view=self)
        await self.callbacker.player_button_call( interaction,"play")'''
    @discord.ui.button(emoji='⏭️',label="skip",style=discord.ButtonStyle.blurple) # or .primary
    async def next_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer()#(content="Next pressed",view=self)
        await self.callbacker.player_button_call(interaction,"next")
        
    @discord.ui.button(emoji='➡️',label="next",style=discord.ButtonStyle.blurple) # or .primary
    async def nextpage_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        if self.pview:
            self.pview.update_display()
            await self.pview.playlistcallback(interaction,self,"next")
        else: await interaction.response.defer()

    @discord.ui.button(emoji='🔀',label="shuffle",style=discord.ButtonStyle.blurple) # or .primary
    async def shuffle_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.playlistcallback(interaction,"shuffle")
        if self.playlistviewmode:
            await interaction.response.edit_message(embed=self.pview.make_embed(),view=self)
        else:
            await interaction.response.edit_message(embed=self.callbacker.get_music_embed('Shuffle','Playlist shuffled.'),view=self)
    @discord.ui.button(emoji='⏹️', label="stop",style=discord.ButtonStyle.red, row=2) # or .primary
    async def exit_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer()#(content="back pressed",view=self)
        await self.callbacker.player_button_call( interaction,"stop")
    @discord.ui.button(emoji='⬆️',label="PlaylistOpen",style=discord.ButtonStyle.blurple) # or .primary
    async def open_playlist(self,interaction:discord.Interaction,button:discord.ui.Button,row=2):
        if self.playlistviewmode==False:
            self.pview=await self.callbacker.playlist_view(interaction)
            self.playlistviewmode=True
            button.label='Close Playlist'
            button.emoji='⬇️'
            self.changenextlast()
            await interaction.response.edit_message(embed=self.pview.make_embed(),view=self)
        else:
            self.pview=None
            #await self.callbacker.player_button_call(interaction,"playlistview")
            self.playlistviewmode=False
            self.changenextlast()
            button.label='Open Playlist'
            button.emoji='⬆️'
            await interaction.response.edit_message(embed=self.callbacker.get_music_embed('Hidden','Playlist disabled.'),view=self)
    
        
        #await self.callbacker.player_button_call(interaction,"playlistview")
        


class PlaylistButtons(discord.ui.View):
    '''buttons for the playlist operation.'''
    def __init__(self, *, timeout=180, callback=None):
        super().__init__(timeout=timeout)
        self.callbacker=callback
    @discord.ui.button(emoji='*️⃣', label="exit",style=discord.ButtonStyle.blurple) # or .primary
    async def exit_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.playlistcallback(interaction,self,"exit")
    
    @discord.ui.button(emoji='↩️',label="first",style=discord.ButtonStyle.blurple) # or .primary
    async def first_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.playlistcallback(interaction,self,"first")
    
    @discord.ui.button(emoji='⬅️',label="back",style=discord.ButtonStyle.blurple) # or .primary
    async def back_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.playlistcallback(interaction,self,"back")
    
    @discord.ui.button(emoji='➡️',label="next",style=discord.ButtonStyle.blurple) # or .primary
    async def next_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.playlistcallback(interaction,self,"next")
    
    @discord.ui.button(emoji='↪️',label="final",style=discord.ButtonStyle.blurple) # or .primary
    async def last_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.playlistcallback(interaction,self,"last")
    
    @discord.ui.button(emoji='🔀',label="shuffle",style=discord.ButtonStyle.blurple) # or .primary
    async def shuffle_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.playlistcallback(interaction,self,"shuffle")

    async def on_timeout(self) -> None:
        await self.callbacker.playlistcallback(None,self,"exit")
        return await super().on_timeout()