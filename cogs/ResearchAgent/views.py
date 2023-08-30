import discord
from discord import PartialEmoji


class Followup(discord.ui.View):
    '''buttons for the audio player.'''
    def __init__(self, *, timeout=None,page_content=[]):
        super().__init__(timeout=timeout)
        self.my_sources=page_content
        

    @discord.ui.button(emoji='⬅️',label="view sources",style=discord.ButtonStyle.blurple) # or .primary
    async def showsauce(self,interaction:discord.Interaction,button:discord.ui.Button):
        embed=discord.Embed(title='sauces')
        for doc,score in self.my_sources[:10]:
            #print(doc)
            meta=doc.metadata#'metadata',{'title':'UNKNOWN','source':'unknown'})
            content=doc.page_content #('page_content','Data l
            output=f'''**Name:** {meta['title']}
            **Link:** {meta['source']}
            **Text:** {content}'''
            embed.add_field(name=f's: score:{score}',
                            value=output,
                            inline=False)
        await interaction.response.send_message(embed=embed)
        #await self.callbacker.playlistcallback(interaction,self,"back")
