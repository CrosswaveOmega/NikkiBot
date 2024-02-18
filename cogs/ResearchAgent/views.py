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
        for id, tup in enumerate(self.my_sources[:10]):
            doc, score = tup
            if field_count == 3:
                # Send the embed here or add it to a list of embeds
                # Reset the field count and create a new embed
                field_count = 0
                embeds.append(embed)
                embed = discord.Embed(title="sauces")

            meta = doc.metadata
            content = doc.page_content
            
            output = f"""**ID**:{id}
            **Name:** {meta.get('title','TITLE UNAVAILABLE')[:100]}
            **Link:** {meta['source']}
            **Text:** {content}"""
            embed.add_field(name=f"s: score:{score}", value=output[:1020], inline=False)
            field_count += 1
        embeds.append(embed)
        PCC, buttons = await pages_of_embeds_2("ANY", embeds)

        await interaction.response.send_message(embed=PCC.make_embed(), view=buttons)
        # await self.callbacker.playlistcallback(interaction,self,"back")

class QuestionButton(discord.ui.Button):
    def __init__(self, myvalue=False, **kwargs):
        self.value = myvalue
        super().__init__(**kwargs)

        if self.value:
            self.style = discord.ButtonStyle.green
        else:
            self.style = discord.ButtonStyle.grey

    async def callback(self, interaction: discord.Interaction):
        self.value = not self.value
        await self.view.destroy_button(self.custom_id,interaction)


class Questions(discord.ui.View):
    """followup questions"""

    def __init__(self, *, bot=None, timeout=None, questions=[]):
        super().__init__(timeout=timeout)
        self.questions = questions
        self.bot = bot
        self.question_buttons=[]

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item
    ) -> None:
        gui.gprint(str(error))
        await self.bot.send_error(error, "followuperror")
        # await interaction.response.send_message(f'Oops! Something went wrong: {str(error)}.', ephemeral=True)

    async def create_question_buttons(self, inter: discord.Interaction):
        for e,q in enumerate(self.questions):
            val = False
            button = QuestionButton(label=q, custom_id=f"quest+{e}", myvalue=val)
            self.question_buttons.append(button)
            self.add_item(button)
        await inter.edit_original_response(view=self)

    async def destroy_button(self, custom_id,inter: discord.Interaction):
        for button in self.question_buttons:
            if button.custom_id==custom_id:
                self.remove_item(button)
        await inter.edit_original_response(view=self)

