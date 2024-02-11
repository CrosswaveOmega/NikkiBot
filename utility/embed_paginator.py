import discord
from discord.ext import commands
from typing import List, Tuple
from discord import Embed
import gui

"""This is for returning pages of embeds"""


class PageSelect(discord.ui.Select):
    """Simple Dropdown Menu that"""

    def __init__(self, option_pass, page):
        options = option_pass
        super().__init__(
            placeholder=f"Select an option (you are page {page})",
            max_values=1,
            min_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        # if self.values[0] == "Option 1":
        value = self.values[0]
        for f in self.options:
            if f.value == value:
                f.default = True
            else:
                f.default = False
        await self.view.selectcall(interaction, self)


class PageClassContainer:
    def __init__(self, display: List[Embed] = []):
        """
        A class representing a container for displaying a list of embeds with pagination.

        Args:
        - display: a list of Embed objects to be displayed
        """
        self.display = display
        self.spot = 0
        self.perpage = 1
        self.length = len(self.display)
        self.largest_spot = ((self.length - 1) // self.perpage) * self.perpage
        self.maxpages = ((self.length - 1) // self.perpage) + 1
        self.custom_callbacks = {}
        self.page = (self.spot // self.perpage) + 1

    async def generate_select(self):
        selectlist = []
        for e, i in enumerate(self.display):
            selectlist.append(
                discord.SelectOption(
                    label=f"{i.title}, Page: {e}",
                    description="Go to page {e}",
                    value=e,
                    default=True if self.page - 1 == e else False,
                )
            )
        s = PageSelect(selectlist, self.page)
        return s

    def make_embed(self) -> Embed:
        """
        Create an Embed object with the current page's content.

        Returns:
        - An Embed object
        """
        self.page = (self.spot // self.perpage) + 1
        key = ""
        gui.gprint(len(self.display), self.page)
        emb = Embed(title="No Pages")
        if len(self.display) > 0:
            emb = self.display[self.page - 1]
        emb.set_author(
            name=" Page {}/{}, {} total".format(self.page, self.maxpages, self.length)
        )
        return emb

    def set_display(self, display: List[Embed] = []):
        """
        Set the list of Embeds to be displayed and update relevant variables.

        Args:
        - display: a list of Embed objects to be displayed
        """
        self.display = display
        self.length = len(self.display)
        self.largest_spot = ((self.length - 1) // self.perpage) * self.perpage
        self.maxpages = ((self.length - 1) // self.perpage) + 1
        self.custom_callbacks = {}
        self.page = (self.spot // self.perpage) + 1

    def add_custom_callback(self, name: str, call: callable):
        """
        Add a custom callback function to be called when a specific button is clicked.

        Args:
        - name: the name of the button to trigger the callback
        - call: the callback function to be called
        """
        self.custom_callbacks[name] = call

    async def mycallback(
        self,
        interaction: discord.Interaction,
        view: discord.ui.View,
        result: str,
        goto: int = 0,
    ) -> None:
        """
        Callback function for the UI button interaction.

        Args:
            interaction (discord.Interaction): The interaction object that triggered the callback.
            view (discord.ui.View): The view object that contains the UI buttons.
            result (str): The custom_id of the button that was clicked.
        """
        if result in ("timeout", "exit"):
            ve = view.clear_items()
            await interaction.response.edit_message(content="done", view=ve)
        else:
            if result in self.custom_callbacks:
                await self.custom_callbacks[result](self, interaction, view, result)
            if result == "next":
                self.spot = (self.spot + self.perpage) % self.length
            elif result == "back":
                self.spot = (self.spot - self.perpage + self.length) % self.length
            elif result == "first":
                self.spot = 0
            elif result == "last":
                self.spot = self.largest_spot
            elif result == "goto":
                self.spot = goto % self.length

            emb = self.make_embed()
            await interaction.response.edit_message(embed=emb, view=view)


class EmbedPageButtons(discord.ui.View):
    def __init__(self, *, timeout: int = 180, callbacker: PageClassContainer) -> None:
        super().__init__(timeout=timeout)
        self.callbacker = callbacker
        self.pageselect = None

    async def selectcall(self, interaction, select: PageSelect):
        await self.callbacker.mycallback(
            interaction, self, "goto", int(select.values[0])
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
            self.pagebutton_button = None
            self.pageselect = None
        await self.callbacker.mycallback(interaction, self, "pass")

    # Exit button
    @discord.ui.button(emoji="⏹️", label="exit", style=discord.ButtonStyle.blurple)
    async def exit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Call mycallback method of the callbacker object with "exit" argument
        await self.callbacker.mycallback(interaction, self, "exit")

    # First button
    @discord.ui.button(emoji="⏮️", label="first", style=discord.ButtonStyle.blurple)
    async def first_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Call mycallback method of the callbacker object with "first" argument
        await self.callbacker.mycallback(interaction, self, "first")

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

    # Final button
    @discord.ui.button(emoji="⏭️", label="final", style=discord.ButtonStyle.blurple)
    async def last_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Call mycallback method of the callbacker object with "last" argument
        await self.callbacker.mycallback(interaction, self, "last")


class SelectView(discord.ui.View):
    # This is a view for the navigation buttons.
    def __init__(self, *, timeout=180, myhelp=None):
        super().__init__(timeout=timeout)
        self.add_item(EmbedPageButtons())


async def pages_of_embeds_2(
    ctx: commands.Context, display: List[discord.Embed]
) -> Tuple[PageClassContainer, EmbedPageButtons]:
    """
    Creates a PageClassContainer and a EmbedPageButtons object and returns them as a tuple.
    This function is similar to pages_of_embeds() but returns 
    the EmbedPageButtons object along with the PageClassContainer without sending a 
    new message to discord.

    Parameters:
    -----------
    ctx: commands.Context
        The context object of the message that triggered the command.
    display: List[discord.Embed]
        A list of Embed objects and a string.

    Returns:
    --------
    A tuple containing:
    pagecall: PageClassContainer
        An instance of PageClassContainer containing the `display` list.
    buttons: EmbedPageButtons
        An instance of the EmbedPageButtons class with a reference to the `pagecall` instance.
    """
    pagecall = PageClassContainer(display)

    buttons = EmbedPageButtons(callbacker=pagecall)
    return pagecall, buttons


async def pages_of_embeds(
    ctx: commands.Context, display: List[discord.Embed], **kwargs
) -> discord.Message:
    """
    Creates a new PageClassContainer filled with embeds, and sends it as 
     a message with buttons.

    Parameters:
    -----------
    ctx: commands.Context
        The context object of the message that triggered the command.
    display: List[discord.Embed]
        A list of Embeds.
    kwargs: Keyword arguments for discord.message.

    Returns:
    --------
    A Message object sent to the channel where the command was triggered.
    """

    pagecall = PageClassContainer(display)
    message = await ctx.send(
        embed=pagecall.make_embed(),
        view=EmbedPageButtons(callbacker=pagecall),
        **kwargs,
    )
    return message
