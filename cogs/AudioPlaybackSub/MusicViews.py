import discord
from discord import PartialEmoji
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
        self.playpausemode=''
        self.setplaypause()
        self.changenextlast()

    def setplaypause(self):
        
        if  self.callbacker.player_condition=='play':
            self.playpause_button.emoji='⏸'
            self.playpausemode='pause'
            #return 'play'
        else:
            self.playpause_button.emoji='▶️'
            self.playpausemode='play'
            #return 'pause'
    
    def changenextlast(self):
        if  self.playlistviewmode:
            self.backpage_button.emoji=PartialEmoji.from_str("a:trianglepointerleft:1133097547645341848")
            #'⬅️'
            
            #'➡️'
            self.nextpage_button.emoji=PartialEmoji.from_str("a:trianglepointer:1132773635195686924")
            self.backpage_button.label=''
            self.nextpage_button.label=''
        else:
            self.backpage_button.emoji=None
            self.nextpage_button.emoji=None
            self.backpage_button.label='_ _'
            self.nextpage_button.label='_ _'
    async def updateview(self,inter:discord.Interaction):
        self.setplaypause()
        self.changenextlast()
        await inter.edit_original_response(view=self)
    @discord.ui.button(emoji='⬅️',label="",style=discord.ButtonStyle.blurple) # or .primary
    async def backpage_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        if self.pview:
            self.pview.update_display()
            await self.pview.playlistcallback(interaction,self,"back")
        else: await interaction.response.defer()
        #await self.callbacker.playlistcallback(interaction,self,"back")

    @discord.ui.button(emoji='⏮️',label="",style=discord.ButtonStyle.blurple) # or .primary
    async def back_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer()#(content="back pressed",view=self)
        await self.callbacker.player_button_call(interaction,"back")
    @discord.ui.button(emoji='⏯',label="",style=discord.ButtonStyle.blurple) # or .primary
    async def playpause_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        #await interaction.response.defer()#(content="Next pressed",view=self)
        await interaction.response.send_message(f'{self.playpausemode}, give it a second.',ephemeral=True)
        await self.callbacker.player_button_call( interaction,self.playpausemode)
        await self.updateview(interaction)
    '''@discord.ui.button(emoji='▶️',label="play",style=discord.ButtonStyle.blurple) # or .primary
    async def play_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer()#(content="Next pressed",view=self)
        await self.callbacker.player_button_call( interaction,"play")'''
    @discord.ui.button(emoji='⏭️',label="",style=discord.ButtonStyle.blurple) # or .primary
    async def next_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer()#(content="Next pressed",view=self)
        await self.callbacker.player_button_call(interaction,"next")
        
    @discord.ui.button(emoji='➡️',label="",style=discord.ButtonStyle.blurple) # or .primary
    async def nextpage_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        if self.pview:
            self.pview.update_display()
            await self.pview.playlistcallback(interaction,self,"next")
        else: await interaction.response.defer()

    @discord.ui.button(emoji='🔀',label="",style=discord.ButtonStyle.blurple,row=1) # or .primary
    async def shuffle_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.playlistcallback(interaction,"shuffle")
        if self.playlistviewmode:
            await interaction.response.edit_message(embed=self.pview.make_embed(),view=self)
        else:
            await interaction.response.edit_message(embed=self.callbacker.get_music_embed('Shuffle','Playlist shuffled.'),view=self)
    @discord.ui.button(emoji='⏹️', label="",style=discord.ButtonStyle.red, row=3) # or .primary
    async def exit_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer()#(content="back pressed",view=self)
        await self.callbacker.player_button_call( interaction,"stop")
    @discord.ui.button(emoji=PartialEmoji.from_str("playlist2:1133094676019294268"),label="view",style=discord.ButtonStyle.blurple) # or .primary
    async def open_playlist(self,interaction:discord.Interaction,button:discord.ui.Button,row=1):
        if self.playlistviewmode==False:
            self.pview=await self.callbacker.playlist_view(interaction)
            self.playlistviewmode=True
            button.label='hide'
            button.emoji=PartialEmoji.from_str("playlist2:1133094676019294268")
            self.changenextlast()
            await interaction.response.edit_message(embed=self.pview.make_embed(),view=self)
        else:
            self.pview=None
            #await self.callbacker.player_button_call(interaction,"playlistview")
            self.playlistviewmode=False
            self.changenextlast()
            button.label='view'
            button.emoji=PartialEmoji.from_str("playlist2:1133094676019294268")
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