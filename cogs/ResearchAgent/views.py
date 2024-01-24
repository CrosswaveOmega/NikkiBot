import discord
from discord import PartialEmoji
import gui
from utility import pages_of_embeds_2


class Followup(discord.ui.View):
    """buttons for the audio player."""

    def __init__(self, *, bot=None, timeout=None, page_content=[]):
        super().__init__(timeout=timeout)
        self.my_sources = page_content
        self.bot = bot

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item
    ) -> None:
        gui.gprint(str(error))
        await self.bot.send_error(error, "followuperror")
        # await interaction.response.send_message(f'Oops! Something went wrong: {str(error)}.', ephemeral=True)

    @discord.ui.button(
        emoji="⬅️", label="view sources", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def showsauce(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(title="sauces")
        field_count = 0
        embeds = []
        for id,tup in enumerate(self.my_sources[:10]):
            doc, score=id
            if field_count == 3:
                # Send the embed here or add it to a list of embeds
                # Reset the field count and create a new embed
                field_count = 0
                embeds.append(embed)
                embed = discord.Embed(title="sauces")

            meta = doc.metadata
            content = doc.page_content
            output = f"""**ID**:{id}
            **Name:** {meta['title'][:100]}
            **Link:** {meta['source']}
            **Text:** {content}"""
            embed.add_field(name=f"s: score:{score}", value=output[:1020], inline=False)
            field_count += 1
        embeds.append(embed)
        PCC, buttons = await pages_of_embeds_2("ANY", embeds)

        await interaction.response.send_message(embed=PCC.make_embed(), view=buttons)
        # await self.callbacker.playlistcallback(interaction,self,"back")
