import discord

class PlayerButtons(discord.ui.View):
    '''buttons for the audio player.'''
    def __init__(self, *, timeout=180, inter=None, callback=None):
        super().__init__(timeout=timeout)
        self.callbacker=callback
        self.inter=inter
    @discord.ui.button(emoji='⏹️', label="stop",style=discord.ButtonStyle.red) # or .primary
    async def exit_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.mycallback( self.inter,"stop")
        await interaction.response.edit_message(content="Stop pressed",view=self)
    @discord.ui.button(emoji='⏮️',label="back",style=discord.ButtonStyle.blurple) # or .primary
    async def back_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.mycallback(self.inter,"back")
        await interaction.response.edit_message(content="back pressed",view=self)
    @discord.ui.button(emoji='⏸',label="pause",style=discord.ButtonStyle.blurple) # or .primary
    async def pause_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.mycallback( self.inter,"pause")
        await interaction.response.edit_message(content="Pause pressed",view=self)
    @discord.ui.button(emoji='▶️',label="play",style=discord.ButtonStyle.blurple) # or .primary
    async def play_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.mycallback( self.inter,"play")
        await interaction.response.edit_message(content="Play pressed",view=self)
    @discord.ui.button(emoji='⏭️',label="skip",style=discord.ButtonStyle.blurple) # or .primary
    async def next_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.callbacker.mycallback(self.inter,"next")
        await interaction.response.edit_message(content="Next pressed",view=self)


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