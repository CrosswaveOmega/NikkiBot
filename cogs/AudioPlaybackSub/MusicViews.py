import discord
from discord import PartialEmoji
from .AudioContainer import AudioContainer


class AddSong(discord.ui.Modal, title="Enter your songs here."):
    """this modal is for making the Poll name and Description."""

    SongList = discord.ui.TextInput(
        label="Paste the song urls below.",
        style=discord.TextStyle.paragraph,
        placeholder="Enter the urls of every song you want to add to the queue here.  Each url must be on it's own line.",
        required=True,
        max_length=512,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = None

    async def on_submit(self, interaction):
        songtext = self.SongList.value
        self.done = {}
        self.done["songs"] = songtext
        await interaction.response.defer()
        self.stop()


class PlayerButtons(discord.ui.View):
    """buttons for the audio player."""

    def __init__(self, *, timeout=None, inter=None, callback=None):
        super().__init__(timeout=timeout)
        self.callbacker = callback
        self.inter = inter
        self.playlistviewmode = False
        self.pview = None
        self.playpausemode = ""
        self.setplaypause()
        self.changenextlast()
        self.repeat_toggle()

    def repeat_toggle(self):
        if self.callbacker.repeat == True:
            self.repeat_button.style = discord.ButtonStyle.gray
        else:
            self.repeat_button.style = discord.ButtonStyle.blurple

    def setplaypause(self):
        if self.callbacker.player_condition == "play":
            self.playpause_button.emoji = "⏸"
            self.playpausemode = "pause"
            # return 'play'
        else:
            self.playpause_button.emoji = "▶️"
            self.playpausemode = "play"
            # return 'pause'

    def changenextlast(self):
        if self.playlistviewmode:
            self.backpage_button.emoji = PartialEmoji.from_str(
                "a:trianglepointerleft:1133097547645341848"
            )
            # '⬅️'

            # '➡️'
            self.nextpage_button.emoji = PartialEmoji.from_str(
                "a:trianglepointer:1132773635195686924"
            )
            self.backpage_button.label = ""
            self.nextpage_button.label = ""
        else:
            self.backpage_button.emoji = None
            self.nextpage_button.emoji = None
            self.backpage_button.label = "_ _"
            self.nextpage_button.label = "_ _"

    async def updateview(self, inter: discord.Interaction = None):
        self.setplaypause()
        self.changenextlast()
        self.repeat_toggle()
        if inter:
            await inter.edit_original_response(content="", view=self)

    @discord.ui.button(
        emoji="⬅️", label="", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def backpage_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.pview:
            self.pview.update_display()
            await self.pview.playlistcallback(interaction, self, "back")
        else:
            await interaction.response.defer()
        # await self.callbacker.playlistcallback(interaction,self,"back")

    @discord.ui.button(
        emoji="⏮️", label="", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()  # (content="back pressed",view=self)
        await self.callbacker.player_button_call(interaction, "back")

    @discord.ui.button(
        emoji="⏯", label="", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def playpause_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # await interaction.response.defer()#(content="Next pressed",view=self)
        orig = interaction.message
        await interaction.response.edit_message(
            content=f"{self.playpausemode} was recieved, give it a second."
        )
        await self.callbacker.player_button_call(interaction, self.playpausemode)

        await self.updateview(interaction)

    """@discord.ui.button(emoji='▶️',label="play",style=discord.ButtonStyle.blurple) # or .primary
    async def play_button(self,interaction:discord.Interaction,button:discord.ui.Button):
        await interaction.response.defer()#(content="Next pressed",view=self)
        await self.callbacker.player_button_call( interaction,"play")"""

    @discord.ui.button(
        emoji="⏭️", label="", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()  # (content="Next pressed",view=self)
        await self.callbacker.player_button_call(interaction, "next")

    @discord.ui.button(
        emoji="➡️", label="", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def nextpage_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.pview:
            self.pview.update_display()
            await self.pview.playlistcallback(interaction, self, "next")
        else:
            await interaction.response.defer()

    @discord.ui.button(
        emoji="🔀", label="", style=discord.ButtonStyle.blurple, row=1
    )  # or .primary
    async def shuffle_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Shuffle all songs in the queue."""
        await self.callbacker.playlistcallback(interaction, "shuffle")
        if self.playlistviewmode:
            await interaction.response.edit_message(
                embed=self.pview.make_embed(), view=self
            )
        else:
            await interaction.response.edit_message(
                embed=self.callbacker.get_music_embed("Shuffle", "Playlist shuffled."),
                view=self,
            )

    @discord.ui.button(
        emoji="🔁", label="", style=discord.ButtonStyle.grey, row=1
    )  # or .primary
    async def repeat_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.callbacker.playlistcallback(interaction, "repeat")

        await self.updateview()
        await interaction.response.edit_message(
            embed=self.callbacker.get_music_embed("Shuffle", "repeat toggled"),
            view=self,
        )

    @discord.ui.button(
        emoji="⏹️", label="", style=discord.ButtonStyle.red, row=3
    )  # or .primary
    async def exit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()  # (content="back pressed",view=self)
        await self.callbacker.player_button_call(interaction, "stop")

    @discord.ui.button(
        emoji=PartialEmoji.from_str("playlist2:1133094676019294268"),
        label="",
        style=discord.ButtonStyle.blurple,
    )  # or .primary
    async def open_playlist(
        self, interaction: discord.Interaction, button: discord.ui.Button, row=1
    ):
        if self.playlistviewmode == False:
            self.pview = await self.callbacker.playlist_view(interaction)
            self.playlistviewmode = True
            # button.label='hide'
            button.emoji = PartialEmoji.from_str("playlistclose:1135616781063565343")
            self.changenextlast()
            await interaction.response.edit_message(
                embed=self.pview.make_embed(), view=self
            )
        else:
            self.pview = None
            # await self.callbacker.player_button_call(interaction,"playlistview")
            self.playlistviewmode = False
            self.changenextlast()
            # button.label='view'
            button.emoji = PartialEmoji.from_str("playlistopen:1135616782254743663")
            await interaction.response.edit_message(
                embed=self.callbacker.get_music_embed("Hidden", "Playlist disabled."),
                view=self,
            )

    #
    @discord.ui.button(
        emoji=PartialEmoji.from_str("noteadd:1135620202856464545"),
        label="",
        style=discord.ButtonStyle.blurple,
    )  # or .primary
    async def addsong(
        self, interaction: discord.Interaction, button: discord.ui.Button, row=1
    ):
        name_modal = AddSong(timeout=5 * 60)
        await interaction.response.send_modal(name_modal)
        await name_modal.wait()
        if name_modal.done != None:
            songs = name_modal.done["songs"]
            slist = songs.split("\n")
            add = err = 0
            errs = []
            for s in slist:
                try:
                    result = await self.callbacker.playlist_actions(
                        "add_url",
                        param=(s, interaction.user),
                        do_search=False,
                        ignore_error=True,
                    )
                    if not isinstance(result, AudioContainer):
                        errs.append(f"`{s}`: {result}")
                    else:
                        add += 1
                except Exception as e:
                    print(e)
                    err += 1
            if not errs:
                await interaction.edit_original_response(
                    content=f"Added all {add} Songs"
                )
            else:
                output = "\n".join(errs)
                await interaction.edit_original_response(
                    content=f"Added {add} Songs, except for...\n{output}"
                )
        else:
            await interaction.edit_original_response(content="cancelled")


class PlaylistButtons(discord.ui.View):
    """buttons for the playlist operation."""

    def __init__(self, *, timeout=180, callback=None):
        super().__init__(timeout=timeout)
        self.callbacker = callback

    @discord.ui.button(
        emoji="*️⃣", label="exit", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def exit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.callbacker.playlistcallback(interaction, self, "exit")

    @discord.ui.button(
        emoji="↩️", label="first", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def first_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.callbacker.playlistcallback(interaction, self, "first")

    @discord.ui.button(
        emoji="⬅️", label="back", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def back_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.callbacker.playlistcallback(interaction, self, "back")

    @discord.ui.button(
        emoji="➡️", label="next", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.callbacker.playlistcallback(interaction, self, "next")

    @discord.ui.button(
        emoji="↪️", label="final", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def last_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.callbacker.playlistcallback(interaction, self, "last")

    @discord.ui.button(
        emoji="🔀", label="shuffle", style=discord.ButtonStyle.blurple
    )  # or .primary
    async def shuffle_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.callbacker.playlistcallback(interaction, self, "shuffle")

    async def on_timeout(self) -> None:
        await self.callbacker.playlistcallback(None, self, "exit")
        return await super().on_timeout()
