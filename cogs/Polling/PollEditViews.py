import gui
from typing import Any, Coroutine
import discord
from discord.interactions import Interaction
from assets import AssetLookup


class Poll_Choice_Make(discord.ui.Modal, title="Edit your poll choices."):
    """This modal is for editing poll choices."""

    def __init__(self, scope: str, choices: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None
        self.scope = scope
        self.choices = choices
        self.choice_a = discord.ui.TextInput(
            label="Choice A", max_length=32, required=True
        )
        self.choice_b = discord.ui.TextInput(
            label="Choice B", max_length=32, required=True
        )
        self.add_item(self.choice_a)
        self.add_item(self.choice_b)
        if self.choices >= 3:
            self.choice_c = discord.ui.TextInput(
                label="Choice C", max_length=32, required=True
            )
            self.add_item(self.choice_c)
        if self.choices >= 4:
            self.choice_d = discord.ui.TextInput(
                label="Choice D", max_length=32, required=True
            )
            self.add_item(self.choice_d)
        if self.choices == 5:
            self.choice_e = discord.ui.TextInput(
                label="Choice E", max_length=32, required=True
            )
            self.add_item(self.choice_e)

    async def on_submit(self, interaction):
        choices = [
            (c, getattr(self, f"choice_{c}").value) for c in "abcde"[: self.choices]
        ]
        self.done = {}
        self.done["choices"] = choices
        await interaction.response.defer()
        self.stop()


class Poll_Name_Make(discord.ui.Modal, title="Create a Poll"):
    """this modal is for making the Poll name and Description."""

    PollName = discord.ui.TextInput(
        label="Poll Title",
        placeholder="give a short title for your poll here!",
        max_length=50,
        required=True,
    )

    PollText = discord.ui.TextInput(
        label="Poll Description",
        style=discord.TextStyle.paragraph,
        placeholder="Enter a description for your Poll here.",
        required=True,
        max_length=256,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None

    async def on_submit(self, interaction):
        poll_text = self.PollText.value
        poll_name = self.PollName.value
        self.done = {}
        self.done["poll_text"] = poll_text
        self.done["poll_name"] = poll_name
        await interaction.response.defer()
        self.stop()


class Dropdown(discord.ui.Select):
    def __init__(self, option_kwarg, this_label="default", key="", user=None):
        self.user = user
        options = []
        for i in option_kwarg:
            options.append(discord.SelectOption(**i))

        self.key = key
        super().__init__(
            placeholder=this_label, min_values=1, max_values=1, options=options
        )

    async def interaction_check(self, interaction: Interaction[discord.Client]):
        if interaction.user == self.user:
            return True
        return False

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        gui.gprint(str(error))
        await interaction.response.send_message(
            f"Oops! Something went wrong: {str(error)}.", ephemeral=True
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        for f in self.options:
            if f.value == value:
                f.default = True
            else:
                f.default = False
        if self.key in self.view.my_poll:
            self.view.my_poll[self.key] = int(value)
        outcome = f"Updated {self.key} to {value}."
        await interaction.response.edit_message(
            content=f"{value}", embed=format_poll_embed(self.view.my_poll, outcome)
        )


def format_poll_embed(poll_dict, op_status=""):
    """create an embed to dispay the work in progress poll!"""
    choices = poll_dict["choices"]
    pollname = poll_dict["poll_name"]
    polltext = poll_dict["poll_text"]

    # Create Embed object
    embed = discord.Embed(title=pollname, description=polltext)

    embed.set_author(
        name="Polling System", icon_url=AssetLookup.get_asset("embed_icon")
    )
    # Add choices to embed based on how many were specified
    if choices >= 2:
        embed.add_field(name="Choice A", value=poll_dict["choice_a"], inline=False)
        embed.add_field(name="Choice B", value=poll_dict["choice_b"], inline=False)
    if choices >= 3:
        embed.add_field(name="Choice C", value=poll_dict["choice_c"], inline=False)
    if choices >= 4:
        embed.add_field(name="Choice D", value=poll_dict["choice_d"], inline=False)
    if choices >= 5:
        embed.add_field(name="Choice E", value=poll_dict["choice_e"], inline=False)

    # Add duration to embed if specified
    days = poll_dict["days"]
    hours = poll_dict["hours"]
    minutes = poll_dict["minutes"]
    if days > 0 or hours > 0 or minutes > 0:
        duration_str = f"{days} day{'s' if days != 1 else ''}, {hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
        embed.add_field(
            name="Poll Duration:", value=f"Poll duration: {duration_str}", inline=False
        )
    if op_status:
        embed.add_field(name="[STATUS]", value=op_status)
    embed.set_footer(
        text=f"Scope: {poll_dict['scope']},  Server_ID: {poll_dict['server_id']}"
    )
    return embed


class PollEdit(discord.ui.View):
    my_poll = {
        "choices": 2,
        "days": 1,
        "hours": 0,
        "minutes": 0,
        "poll_name": "",
        "poll_text": "",
        "choice_a": "",
        "choice_b": "",
        "choice_c": "",
        "choice_d": "",
        "choice_e": "",
        "scope": "",
        "server_id": "",
    }
    value = False

    def __init__(self, *, user, timeout=30 * 15, scope="server", server_id=0):
        super().__init__(timeout=timeout)
        self.user = user
        self.my_poll["scope"] = scope
        self.my_poll["server_id"] = server_id
        self.my_dropdown = Dropdown(
            [
                {"label": "2", "description": "Two Options"},
                {"label": "3", "description": "Three Options"},
                {"label": "4", "description": "Four Options"},
                {"label": "5", "description": "Five Options"},
            ],
            "Number of poll choices",
            "choices",
            user=self.user,
        )
        self.add_item(self.my_dropdown)
        days_list = []
        for i in range(0, 8):
            days_list.append({"label": i, "description": f"last for {i} days."})
        self.time_dropdown = Dropdown(
            days_list, "Days poll will last.", "days", user=self.user
        )
        self.add_item(self.time_dropdown)
        hours_list = []
        for i in range(0, 24):
            hours_list.append({"label": i, "description": f"last for {i} hours."})
        self.hours_drop = Dropdown(
            hours_list, "Hours poll will last.", "hours", user=self.user
        )
        self.add_item(self.hours_drop)

    async def interaction_check(self, interaction: Interaction[discord.Client]):
        if interaction.user == self.user:
            return True
        return False

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        gui.gprint(str(error))
        await interaction.response.send_message(
            f"Oops! Something went wrong: {str(error)}.", ephemeral=True
        )

    @discord.ui.button(label="Edit Name and Text", style=discord.ButtonStyle.blurple)
    async def nameedit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """
        Send a modal to let users customize the name and description of the poll.
        """
        name_modal = Poll_Name_Make(timeout=5*60)
        await interaction.response.send_modal(name_modal)
        await name_modal.wait()
        if name_modal.done != None:
            self.my_poll["poll_name"] = name_modal.done["poll_name"]
            self.my_poll["poll_text"] = name_modal.done["poll_text"]
            emb = format_poll_embed(self.my_poll)
            await interaction.edit_original_response(
                content="Name has been edited.",
                embed=format_poll_embed(self.my_poll, "Name and description updated."),
            )
        else:
            await interaction.edit_original_response(
                content="cancelled",
                embed=format_poll_embed(self.my_poll, "Modal change cancelled."),
            )

    @discord.ui.button(label="Edit Poll Choices", style=discord.ButtonStyle.blurple)
    async def choiceedit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """
        Send a modal to let users customize the poll choices.
        """
        choice_modal = Poll_Choice_Make(
            scope="NA", choices=int(self.my_poll["choices"]), timeout=5*60
        )
        await interaction.response.send_modal(choice_modal)
        await choice_modal.wait()
        if choice_modal.done != None:
            for i in choice_modal.done["choices"]:
                c, e = i
                self.my_poll[f"choice_{c}"] = e
            await interaction.edit_original_response(
                content="Choices_edited",
                embed=format_poll_embed(self.my_poll, "Updated the poll choices."),
            )
        else:
            await interaction.edit_original_response(
                content="cancel",
                embed=format_poll_embed(self.my_poll, "Choices modal closed out."),
            )

    def complete_check(self):
        """
        This is a function that checks if the current my_poll dictionary
        has all the necessary information filled out to be considered "complete".
        If any required fields are missing,
        the function will return a message indicating which fields are missing.
         If everything is filled out, the function will return "OK".

            Returns:
            - str: A message indicating whether the poll is complete or not.
                   If this is "OK." then it's complete.

            Other Parameters:
            - self: The class instance to which this function belongs.
        """
        if not self.my_poll["poll_name"]:
            return "Enter a name!"
        if not self.my_poll["poll_text"]:
            return "Enter a poll description."
        # Check if each choice attribute up to choices is filled
        for i in range(1, self.my_poll["choices"] + 1):
            if not self.my_poll["choice_" + chr(ord("a") + i - 1)]:
                return f"You need to fill out {'choice_' + chr(ord('a') + i - 1)}"

        total_time = (
            self.my_poll["days"] * 24 * 60
            + self.my_poll["hours"] * 60
            + self.my_poll["minutes"]
        )
        if total_time <= 0:
            return "This poll will be over the moment you press confirm!  Specify a duration!"
        return "OK"

    @discord.ui.button(label="Submit Poll", style=discord.ButtonStyle.green, row=4)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Make sure the my_poll dictionary is filled out, and return."""
        cc = self.complete_check()
        if cc != "OK":
            await interaction.response.edit_message(
                content=cc, embed=format_poll_embed(self.my_poll, cc)
            )
        else:
            await interaction.response.edit_message(
                content="Making your poll...",
                embed=format_poll_embed(self.my_poll, "Completed!  Making your poll."),
            )
            self.value = True
            self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label="Discard Poll", style=discord.ButtonStyle.grey, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Canceled",
            embed=format_poll_embed(self.my_poll, "Operation cancelled."),
        )
        self.value = False
        self.stop()
