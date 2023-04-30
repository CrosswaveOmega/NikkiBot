import discord
from .PollingTables import PollTable
class PollVoteButton(discord.ui.Button['PollVoteButton']):
        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)
        async def callback(self, interaction: discord.Interaction):
            user=interaction.user
            button_id=self.custom_id
            print(user.id,button_id)
            outcome,poll=PollTable.vote(button_id,user.id)
            print("next")
            #poll=PollTable.get(p)
            #await interaction.edit_original_response(embed=poll.poll_embed_view())
            await interaction.response.edit_message(embed=poll.poll_embed_view())
        async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
            await interaction.response.send_message(f'Error: {str(error)}', ephemeral=True)


class Persistent_Poll_View(discord.ui.View):
    def __init__(self,poll):
        super().__init__(timeout=None)
        self.poll_id=poll.poll_id
        self.my_count={}
        buttons=poll.poll_buttons()
        for e,b in enumerate(buttons):
            id,text=b
            button=PollVoteButton(label=text,style=discord.ButtonStyle.primary,custom_id=id,row=e)
            self.add_item(button)
        
