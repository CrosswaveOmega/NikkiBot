from typing import Any, Coroutine
import discord
from discord.interactions import Interaction
class ConfirmView(discord.ui.View):
    value=False
    user=None
    def __init__(self, *, user:discord.User,timeout=30*15):
        super().__init__(timeout=timeout)
        self.user=user
        
    async def interaction_check(self, interaction: Interaction[discord.Client]) -> Coroutine[Any, Any, bool]:
        if interaction.user==self.user:
            return True
        return False
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(str(error))
        await interaction.response.send_message(f'Oops! Something went wrong: {str(error)}.', ephemeral=True)

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        '''Make sure the my_poll dictionary is filled out, and return.'''
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        self.stop()