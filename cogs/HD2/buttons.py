import discord
from utility.embed_paginator import PageClassContainer,PageSelect
import logging

class ListButtons(discord.ui.View):
    def __init__(self, *, timeout: int = 180, callbacker: PageClassContainer) -> None:
        super().__init__(timeout=timeout)
        self.callbacker = callbacker
        self.pageselect = None

    async def selectcall(self, interaction, select: PageSelect):
        await self.callbacker.mycallback(
            interaction, self, "goto", int(select.values[0])
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        log = logging.getLogger("discord")

        log.error(
            "Ignoring exception in interaction %s for item %s",
            interaction,
            item,
            exc_info=error,
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"Oops! Something went wrong: {str(error)}.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"Oops! Something went wrong: {str(error)}.", ephemeral=True
            )

    # All button
    @discord.ui.button(emoji="🔢", label="pages", style=discord.ButtonStyle.blurple)
    async def pagebutton_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Call mycallback method of the callbacker object with "exit" argument
        newselect = await self.callbacker.generate_select()
        if not self.pageselect:
            self.pageselect = newselect
            self.add_item(self.pageselect)
        else:
            self.remove_item(self.pageselect)
            # self.pagebutton_button = None
            self.pageselect = None
        await self.callbacker.mycallback(interaction, self, "pass")

    # Exit button
    @discord.ui.button(emoji="⏹️", label="exit", style=discord.ButtonStyle.blurple)
    async def exit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Call mycallback method of the callbacker object with "stop" argument
        await self.callbacker.mycallback(interaction, self, "exit")

    # First button
    # @discord.ui.button(emoji="⏮️", label="first", style=discord.ButtonStyle.blurple)
    # async def first_button(
    #     self, interaction: discord.Interaction, button: discord.ui.Button
    # ) -> None:
    #     # Call mycallback method of the callbacker object with "first" argument
    #     await self.callbacker.mycallback(interaction, self, "first")

    # Back button
    @discord.ui.button(emoji="◀️", label="back", style=discord.ButtonStyle.blurple)
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Call mycallback method of the callbacker object with "back" argument
        await self.callbacker.mycallback(interaction, self, "back")

    # Next button
    @discord.ui.button(emoji="▶️", label="next", style=discord.ButtonStyle.blurple)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Call mycallback method of the callbacker object with "next" argument
        await self.callbacker.mycallback(interaction, self, "next")

    # # Final button
    # @discord.ui.button(emoji="⏭️", label="final", style=discord.ButtonStyle.blurple)
    # async def last_button(
    #     self, interaction: discord.Interaction, button: discord.ui.Button
    # ) -> None:
    #     # Call mycallback method of the callbacker object with "last" argument
    #     await self.callbacker.mycallback(interaction, self, "last")
