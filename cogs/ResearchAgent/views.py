import discord
from discord import PartialEmoji
import gui

class Followup(discord.ui.View):
    '''buttons for the audio player.'''
    def __init__(self, *, bot=None,timeout=None,page_content=[]):
        super().__init__(timeout=timeout)
        self.my_sources=page_content
        self.bot=bot
        
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        gui.gprint(str(error))
        await interaction.response.send_message(f'Oops! Something went wrong: {str(error)}.', ephemeral=True)

    @discord.ui.button(emoji='⬅️',label="view sources",style=discord.ButtonStyle.blurple) # or .primary
    async def showsauce(self,interaction:discord.Interaction,button:discord.ui.Button):
        context =await self.bot.get_context(interaction)
        await context.send('ok')
        embed=discord.Embed(title='sauces')
        for doc,score in self.my_sources[:10]:
            #print(doc)
            meta=doc.metadata#'metadata',{'title':'UNKNOWN','source':'unknown'})
            content=doc.page_content #('page_content','Data l
            output=f'''**Name:** {meta['title'][:100]}
            **Link:** {meta['source']}
            **Text:** {content}'''
            await context.send(output)
            embed.add_field(name=f's: score:{score}',
                            value=output,
                            inline=False)
        await interaction.response.send_message(embed=embed)
        #await self.callbacker.playlistcallback(interaction,self,"back")
