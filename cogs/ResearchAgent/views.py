import discord
from discord import Interaction, PartialEmoji
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
        await self.view.destroy_button(self.custom_id, interaction)


class FollowupAddModal(discord.ui.Modal, title="Add Followup"):
    """Modal for adding a followup."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.followup_input = discord.ui.TextInput(
            label="Followup", max_length=256, required=True
        )
        self.add_item(self.followup_input)

    async def on_submit(self, interaction):
        followup = self.followup_input.value
        self.done = followup
        await interaction.response.defer()
        self.stop()


class FollowupSuggestModal(discord.ui.Modal, title="Suggest"):
    """Modal for suggesting."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.suggestion_input = discord.ui.TextInput(
            label="Suggestion", max_length=256, required=True
        )
        self.add_item(self.suggestion_input)

    async def on_submit(self, interaction):
        suggestion = self.suggestion_input.value
        self.done = suggestion
        await interaction.response.defer()
        self.stop()


class FollowupRemoveModal(discord.ui.Modal, title="Remove Followup"):
    """Modal for removing a followup."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.followup_to_remove_input = discord.ui.TextInput(
            label="Followup to Remove", max_length=256, required=True
        )
        self.add_item(self.followup_to_remove_input)

    async def on_submit(self, interaction):
        followup_to_remove = self.followup_to_remove_input.value
        self.done = followup_to_remove
        await interaction.response.defer()
        self.stop()


class FollowupJustifyModal(discord.ui.Modal, title="Justify"):
    """Modal for justifying."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.justification_input = discord.ui.TextInput(
            label="Justification", max_length=256, required=True
        )
        self.add_item(self.justification_input)

    async def on_submit(self, interaction):
        justification = self.justification_input.value
        self.done = justification
        await interaction.response.defer()
        self.stop()


class FollowupSourceDetailModal(discord.ui.Modal, title="Source Detail"):
    """Modal for source details."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.source_detail_input = discord.ui.NumberInput(
            label="Source Detail", min_value=1, max_value=100, required=True
        )
        self.add_item(self.source_detail_input)

    async def on_submit(self, interaction):
        source_detail = self.source_detail_input.value
        self.done = source_detail
        await interaction.response.defer()
        self.stop()


class FollowupActionView(discord.ui.View):
    def __init__(self, *, user, timeout=30 * 15):
        super().__init__(timeout=timeout)
        self.user = user
        self.value = False

    async def interaction_check(self, interaction: Interaction[discord.Client]):
        return interaction.user == self.user

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        gui.gprint(str(error))
        await interaction.response.send_message(
            f"Oops! Something went wrong: {str(error)}.", ephemeral=True
        )

    @discord.ui.button(
        label="Add Followup",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def add_followup(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = FollowupAddModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done is not None:
            # Assuming there's a function to handle adding followups
            print(modal.done)
            await interaction.edit_original_response(content="Followup added!")
        else:
            await interaction.edit_original_response(
                content="Cancelled",
                embed=discord.Embed(description="Followup addition cancelled."),
            )

    @discord.ui.button(
        label="Suggest",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def suggest(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = FollowupSuggestModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done is not None:
            # Assuming there's a function to handle suggestion
            print(modal.done)
            await interaction.edit_original_response(
                content="Suggestion made!",
                embed=discord.Embed(description=f"Suggested: {modal.done}"),
            )
        else:
            await interaction.edit_original_response(
                content="Cancelled",
                embed=discord.Embed(description="Suggestion cancelled."),
            )

    @discord.ui.button(
        label="Remove Followup",
        style=discord.ButtonStyle.red,
        row=1,
    )
    async def remove_followup(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = FollowupRemoveModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done is not None:
            # Assuming there's a function to handle removing followups
            print(modal.done)
            await interaction.edit_original_response(
                content="Followup removed!",
                embed=discord.Embed(description=f"Removed: {modal.done}"),
            )
        else:
            await interaction.edit_original_response(
                content="Cancelled",
                embed=discord.Embed(description="Followup removal cancelled."),
            )

    @discord.ui.button(
        label="Justify",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def justify(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = FollowupJustifyModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done is not None:
            # Assuming there's a function to handle justification
            print(modal.done)
            await interaction.edit_original_response(
                content="Justification recorded!",
                embed=discord.Embed(description=f"Justified: {modal.done}"),
            )
        else:
            await interaction.edit_original_response(
                content="Cancelled",
                embed=discord.Embed(description="Justification cancelled."),
            )

    @discord.ui.button(
        label="Source Detail",
        style=discord.ButtonStyle.blurple,
        row=2,
    )
    async def source_detail(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = FollowupSourceDetailModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.done is not None:
            # Assuming there's a function to handle source details
            print(modal.done)
            await interaction.edit_original_response(
                content="Source detail recorded!",
                embed=discord.Embed(description=f"Source detail: {modal.done}"),
            )
        else:
            await interaction.edit_original_response(
                content="Cancelled",
                embed=discord.Embed(description="Source detail recording cancelled."),
            )

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.green,
        row=3,
    )
    async def continue_action(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Assuming there's a function to handle continuing

        self.value = True
        await interaction.edit_original_response(content="Continuing...")
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Canceled")
        self.value = False
        self.stop()
