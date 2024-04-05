import logging
from typing import Any, Coroutine
import discord
from discord.interactions import Interaction
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU
import gui

from datetime import datetime, timedelta
import time
from .formatutil import explain_rrule


class ConfirmView(discord.ui.View):
    """This is a simple view for getting a yes/no answer from a user."""

    value = False
    user = None

    def __init__(self, *, user: discord.User, timeout=30 * 15):
        super().__init__(timeout=timeout)
        self.user = user

    async def interaction_check(
        self, interaction: Interaction[discord.Client]
    ) -> Coroutine[Any, Any, bool]:
        if interaction.user == self.user:
            return True
        return False

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        gui.gprint(str(error))
        await interaction.response.send_message(
            f"Oops! Something went wrong: {str(error)}.", ephemeral=True
        )

    async def on_timeout(self) -> None:
        self.value = False
        self.stop()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Make sure the my_poll dictionary is filled out, and return."""
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        self.stop()


class TimeSetModal(discord.ui.Modal, title="Set The Time!"):
    """this modal is for setting the time you want the event to occur at."""

    TimeInput = discord.ui.TextInput(
        label="Time to run (HH:MM, 24 hour format)",
        placeholder="Enter the time you want this event to here (HH:MM)",
        max_length=10,
        required=True,
    )

    def __init__(self, deftime=None, *args, **kwargs):
        dt = deftime
        super().__init__(*args, **kwargs)
        if dt:
            self.TimeInput.default = deftime
        self.done = None

    async def on_submit(self, interaction):
        inputv = self.TimeInput.value
        self.done = inputv
        await interaction.response.defer()
        self.stop()


class IntervalModal(discord.ui.Modal, title="Set the interval"):
    """this modal is for changing the interval."""

    TimeInput = discord.ui.TextInput(
        label="Enter frequency interval.",
        placeholder="How many times do you want this event to run?",
        max_length=100,
        required=True,
    )

    def __init__(self, deftime=None, *args, **kwargs):
        dt = deftime
        super().__init__(*args, **kwargs)
        if dt:
            self.TimeInput.default = deftime
        self.done = None

    async def on_submit(self, interaction):
        inputv = self.TimeInput.value
        self.done = inputv
        await interaction.response.defer()
        self.stop()


class WeekdayButton(discord.ui.Button):
    def __init__(self, myvalue=False, **kwargs):
        self.value = myvalue
        super().__init__(**kwargs)

        if self.value:
            self.style = discord.ButtonStyle.green
        else:
            self.style = discord.ButtonStyle.grey

    async def callback(self, interaction: discord.Interaction):
        self.value = not self.value
        if self.value:
            self.style = discord.ButtonStyle.green

            self.view.dtvals["days"].append(self.custom_id)
        else:
            self.style = discord.ButtonStyle.grey
            self.view.dtvals["days"].remove(self.custom_id)
        gui.gprint(self.value, self.view.dtvals["days"], interaction)
        await interaction.response.edit_message(view=self.view, embed=self.view.emb())


def create_rrule(dtvals):
    freq = dtvals["freq"]
    days = dtvals["days"]
    interval = dtvals["interval"]
    time = dtvals["time"]
    weekday_mapping = {
        "Monday": MO,
        "Tuesday": TU,
        "Wednesday": WE,
        "Thursday": TH,
        "Friday": FR,
        "Saturday": SA,
        "Sunday": SU,
    }
    weekday_constants = [weekday_mapping[day] for day in days]
    # Create the rrule object
    times = datetime.now().replace(second=0)
    if time != None:
        times = datetime.now().replace(hour=time.hour, minute=time.minute, second=0)

    rrule_obj = None

    try:
        rrule_obj = rrule(
            freq, byweekday=weekday_constants, interval=interval, dtstart=times
        )
        return rrule_obj
    except Exception as e:
        return str(e)


def create_rrule_embed(dtvals):
    rrule_obj = create_rrule(dtvals)
    if isinstance(rrule_obj, str):
        return discord.Embed(
            title="Error", description=rrule_obj, color=discord.Color.red()
        )
    # Generate the next four timestamps
    timestamps = []

    gui.gprint("here")
    now = datetime.now()
    for _ in range(4):
        next_timestamp = rrule_obj.after(now)
        if next_timestamp:
            timestamps.append(f"<t:{int(next_timestamp.timestamp())}:F>")
            now = next_timestamp

    # Create the embed
    expl, sent = explain_rrule(rrule_obj)
    embed = discord.Embed(
        title="Current RRule Object",
        description=expl + "\n" + f"{sent}\n`{str(rrule_obj)}`",
        color=discord.Color.green(),
    )
    embed.add_field(
        name="Next four estimated runtimes",
        value="\n".join(map(str, timestamps)),
        inline=False,
    )

    return embed


class RRuleView(discord.ui.View):
    """view that lets you edit a rrule object."""

    timedef = datetime.now().replace(second=0).strftime("%H:%M")

    def __init__(self, user):
        super().__init__()
        self.value = None
        self.user = user
        self.dtvals = {
            "freq": None,
            "days": [],
            "interval": 1,
            "time": datetime.now().replace(second=0).time(),
        }
        self.weekday_buttons = []

    def emb(self):
        return create_rrule_embed(self.dtvals)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    @discord.ui.select(
        placeholder="Select Frequency",
        options=[
            discord.SelectOption(
                label="Daily",
                description="This task will run every day.",
                value="daily",
            ),
            discord.SelectOption(
                label="Weekly",
                description="This task will run on a weekly basis.",
                value="weekly",
            )
            # ,discord.SelectOption(label="Monthly",description="This task will run on a monthly basis.", value="monthly")
        ],
    )
    async def frequency_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        value = select.values[0]
        # Set default.
        for f in select.options:
            if f.value == value:
                f.default = True
            else:
                f.default = False
        # select.placeholder=f"Select Frequency: on{value}"
        lastval = self.dtvals["freq"]
        if value == "daily":
            self.dtvals["freq"] = DAILY
        elif value == "weekly":
            self.dtvals["freq"] = WEEKLY
        elif value == "monthly":
            self.dtvals["freq"] = MONTHLY
        else:
            self.dtvals["freq"] = None

        if self.dtvals["freq"] is None:
            await interaction.response.edit_message(
                content="Invalid selection.", embed=self.emb(), view=self
            )
        else:
            if self.dtvals["freq"] == WEEKLY:
                await interaction.response.edit_message(
                    content=f"Frequency set to {select.values[0]}.  Please make sure to select the days you want to run on below!",
                    embed=self.emb(),
                    view=self,
                )
                if lastval != WEEKLY:
                    await self.create_weekday_buttons(interaction)
            else:
                await interaction.response.edit_message(
                    content=f"Frequency set to {select.values[0]}.",
                    embed=self.emb(),
                    view=self,
                )
                await self.destroy_weekday_buttons(interaction)

    async def create_weekday_buttons(self, inter: discord.Interaction):
        for weekday in [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]:
            val = False
            if weekday in self.dtvals["days"]:
                val = True
            button = WeekdayButton(label=weekday, custom_id=weekday, myvalue=val)
            self.weekday_buttons.append(button)
            self.add_item(button)
        await inter.edit_original_response(view=self)

    async def destroy_weekday_buttons(self, inter: discord.Interaction):
        for button in self.weekday_buttons:
            self.remove_item(button)
        await inter.edit_original_response(view=self)

    @discord.ui.button(
        label=f"Change Time ({timedef})", style=discord.ButtonStyle.blurple, row=3
    )
    async def timeedit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """
        Send a modal to let users customize the name and description of the poll.
        """
        dt = datetime.combine(datetime.min, self.dtvals["time"])
        default = dt.strftime("%H:%M")
        name_modal = TimeSetModal(deftime=default,timeout=5*60)
        await interaction.response.send_modal(name_modal)
        await name_modal.wait()
        gui.gprint("DONE.", name_modal.done)
        if name_modal.done != None:
            timev = name_modal.done
            try:
                timeparse = datetime.strptime(timev, "%H:%M")
                newtime = timeparse.strftime("%H:%M")
                button.label = f"Change Time\n ({newtime})"
                self.dtvals["time"] = timeparse.time()
                await interaction.edit_original_response(
                    content="time is valid", embed=self.emb(), view=self
                )

            except ValueError:
                await interaction.edit_original_response(
                    content="This entered time is not valid!.", embed=self.emb()
                )
        else:
            await interaction.edit_original_response(
                content="Time changing has been cancelled.", embed=self.emb()
            )

    @discord.ui.button(
        label="Change Interval \n(1)", style=discord.ButtonStyle.blurple, row=3
    )
    async def interval(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """
        Send a modal to let users customize the time interval.
        """
        name_modal = IntervalModal(deftime=self.dtvals["interval"],timeout=5*60)
        await interaction.response.send_modal(name_modal)
        await name_modal.wait()
        if name_modal.done != None:
            timev = name_modal.done
            try:
                ival = int(timev)
                if ival <= 0:
                    raise ValueError(f"{ival} can not be negative or zero.")
                elif ival > 10:
                    raise ValueError(
                        f"For the sake of my sanity, please keep this number below 10."
                    )
                self.dtvals["interval"] = ival
                button.label = f"Change Interval \n({ival})"
                await interaction.edit_original_response(
                    content="Valid Interval", embed=self.emb(), view=self
                )

            except ValueError as e:
                await interaction.edit_original_response(
                    content=str(e), embed=self.emb()
                )
        else:
            await interaction.edit_original_response(
                content="Interval Edit Cancelled.", embed=self.emb()
            )

    @discord.ui.button(label="Complete", style=discord.ButtonStyle.green, row=4)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Make sure the my_poll dictionary is filled out, and return."""
        rrule_obj = create_rrule(self.dtvals)
        if isinstance(rrule_obj, str):
            await interaction.response.edit_message(
                content=f"There is an issue with your input!\n{rrule_obj}",
                embed=self.emb(),
            )
        else:
            await interaction.response.edit_message(
                content="complete ", embed=self.emb()
            )
            self.value = rrule_obj
            self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Canceled", embed=self.emb())
        self.value = False
        self.stop()

    async def on_timeout(self):
        self.value = "timeout"
        self.stop()

    async def on_error(self, interaction, error, item):
        # Handle any errors that occur during the interaction
        gui.gprint(error)
        await interaction.response.send_message(f"An error occurred: {error}")


class BaseView(discord.ui.View):
    """Base class for responding views."""

    def __init__(self, *, user, timeout=30 * 15):
        super().__init__(timeout=timeout)
        self.user = user
        self.value = False
        self.timeout_at = discord.utils.utcnow()
        if self.timeout:
            self.timeout_at = discord.utils.utcnow() + timedelta(seconds=self.timeout)

    def update_timeout(self):
        if self.timeout:
            self.timeout_at = discord.utils.utcnow() + timedelta(seconds=self.timeout)

    def get_timeout_dt(self) -> datetime:
        """get timeout datetime."""
        return self.timeout_at

    async def interaction_check(self, interaction: Interaction[discord.Client]):
        return interaction.user == self.user

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        gui.gprint(str(error))
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

    async def on_timeout(self) -> None:
        self.value = False
        self.stop()
