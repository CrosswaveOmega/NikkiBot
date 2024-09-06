from datetime import timedelta
import discord
from discord.ext import commands, tasks
import asyncio
from sqlalchemy.future import select
from cogs.dat_Starboard import (
    TempVCConfig,
)

from discord import app_commands


class VC_Dispatcher(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.my_count = {}
        self.cog: "TempVC" = cog

    async def callback(self, interaction, button):
        user = interaction.user
        label = button.label
        if not str(user.id) in self.my_count:
            self.my_count[str(user.id)] = 0
        self.my_count[str(user.id)] += 1
        await interaction.response.send_message(
            f"You are {user.name}, this is {label}, and you have pressed this button {self.my_count[str(user.id)]} times.",
            ephemeral=True,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            f"Oops! Something went wrong, {str(error)}", ephemeral=True
        )

    @discord.ui.button(
        label="Make New Temp VC",
        style=discord.ButtonStyle.grey,
        emoji="<:add:1199770854112890890>",
        custom_id="MakeNewTempVC:grey",
    )
    async def new_vc(self, interaction: discord.Interaction, button: discord.ui.Button):

        # ctx: commands.Context = await self.bot.get_context(interaction)
        if interaction.guild:
            output = await self.cog.create_temp_vc_2(interaction.guild)
            await interaction.response.send_message(output, ephemeral=True)

        # await self.callback(interaction, button)


class TempVC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temporary_vc_list = {}  # Dictionary to track guild's temporary VCs
        self.temp_vc_num={}
        self.check_empty_vc.start()  # Start the task to check empty voice channels

        self.bot.add_view(VC_Dispatcher(self))

    def cog_unload(self):
        self.check_empty_vc.cancel()

    # Group: Server Configuration

    serverconfig = app_commands.Group(
        name="temp_vc_config",
        description="Commands to configure the temporary VC settings.",
        guild_only=True,
        default_permissions=discord.Permissions(
            manage_messages=True, manage_channels=True
        ),
    )

    @serverconfig.command(
        name="remove_vc", description="Remove the temp vc settings from this server."
    )
    async def remove_vc(self, interaction):
        """Command to remove a vc config for thsi server"""

        ctx: commands.Context = await self.bot.get_context(interaction)
        config = await TempVCConfig.remove_temp_vc_config(ctx.guild.id)
        if config:
            await ctx.send(f"Removed temp vc config.")
        else:
            await ctx.send(
                "No configuration found for this guild. Use `>serverconfig set` first."
            )

    @serverconfig.command(
        name="set",
        description="Command to set the configuration for temporary VCs (category, max users, max channels, and name).",
    )
    async def set_vc_config(
        self,
        interaction,
        category: discord.CategoryChannel,
        max_users: int = 10,
        max_channels: int = 5,
        default_name: app_commands.Range[str, 3, 100] = "temp_vc",
    ):
        """"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        config = await TempVCConfig.get_temp_vc_config(ctx.guild.id)
        if config:
            await ctx.send("Temporary VC configuration is set already.")
            return
        if category is None:
            await ctx.send("Category not found.")
            return

        permissions = category.permissions_for(ctx.guild.me)
        if not (
            permissions.manage_channels
            and permissions.create_instant_invite
            and permissions.mute_members
            and permissions.deafen_members
            and permissions.move_members
            and permissions.view_channel
        ):
            await ctx.send(
                "The bot does not have all necessary permissions for this category."
            )
            return
        if max_channels > 25:
            await ctx.send("The maximum allowed number of channels is 25.")
            return
        if max_channels <= 0:
            await ctx.send("...no you can't have zero or fewer max_channels.")
            return
        if max_users > 99:
            await ctx.send("The maximum allowed number of channels is 99.")
            return
        if max_users <= 0:
            await ctx.send("...no you can't have zero max users.")
            return
        # Store the configuration in the database for this guild
        await TempVCConfig.add_temp_vc_config(
            ctx.guild.id, category.id, max_users, max_channels, default_name
        )
        await ctx.send(
            f"Set the temporary VC config: category = {category.name}, max users = {max_users}, max channels = {max_channels}."
        )

    @serverconfig.command(name="update_max_users")
    async def update_max_users(self, interaction, new_max_users: int):
        """Command to update the max users allowed in temporary VCs."""

        ctx: commands.Context = await self.bot.get_context(interaction)
        config = await TempVCConfig.update_max_users(ctx.guild.id, new_max_users)
        if config:
            await ctx.send(f"Updated max users for temporary VCs to {new_max_users}.")
        else:
            await ctx.send(
                "No configuration found for this guild. Use `>serverconfig set` first."
            )

    @serverconfig.command(name="update_name")
    async def update_vc_name(self, interaction, new_name: str):
        """Command to update the name format of temporary VCs."""

        ctx: commands.Context = await self.bot.get_context(interaction)
        config = await TempVCConfig.update_name(ctx.guild.id, new_name)
        if config:
            await ctx.send(f"Updated temporary VC name format to {new_name}.")
        else:
            await ctx.send(
                "No configuration found for this guild. Use `>serverconfig set` first."
            )

    @serverconfig.command(name="update_max_channels")
    async def update_max_channels(self, interaction, new_max_channels: int):
        """Command to update the max number of temporary VCs allowed."""

        ctx: commands.Context = await self.bot.get_context(interaction)
        if new_max_channels > 25:
            await ctx.send("The maximum allowed number of channels is 25.")
            return
        if new_max_channels <= 0:
            await ctx.send("...no you can't have no max channels.")
            return

        config = await TempVCConfig.update_max_channels(ctx.guild.id, new_max_channels)
        if config:
            await ctx.send(
                f"Updated max channels for temporary VCs to {new_max_channels}."
            )
        else:
            await ctx.send(
                "No configuration found for this guild. Use `>serverconfig set` first."
            )

    # Group: VC Management
    @commands.group(name="vc", invoke_without_command=True)
    async def vc(self, ctx):
        """Base command for managing temporary voice channels."""
        await ctx.send("Use `!vc <subcommand>` for voice channel management.")

    @vc.command(name="dispatch")
    async def make_dispatch(self, ctx: commands.Context):
        """Command to display the dispatcher view that allows users to create temporary VCs."""
        await ctx.send(
            "Click the button below to create a temporary voice channel.\n\nTemporary channels will be deleted if no one joins it in 5 minutes, or if everyone leaves.",
            view=VC_Dispatcher(self),
        )

    async def create_temp_vc_2(
        self, guild: discord.Guild
    ) -> str:
        """Command to create a temporary voice channel in the stored category with stored max users."""
        # Fetch the category and configuration from the database

        config = await TempVCConfig.get_temp_vc_config(guild.id)
        if not config:
            return "Temporary VC configuration is not set. Use `>serverconfig set` to set it."

        # Check if the guild has already reached the max channel limit
        if len(self.temporary_vc_list.get(guild.id, [])) >= config.max_channels:

            return f"Cannot create more than {config.max_channels} temporary voice channels."

        category = discord.utils.get(guild.categories, id=config.category_id)
        if category is None:
            return "Category not found."

        # Create the voice channel with the stored max users
        if guild.id not in self.temporary_vc_list:
            self.temporary_vc_list[guild.id] = [0,[]]

        vc_name = f"{config.target_name}-{self.temporary_vc_list[guild.id][0]+1}"
        self.temporary_vc_list[guild.id][0]+=1
        for vc in category.voice_channels:
            if len(vc.members) == 0:
                return f"There is already an empty VC: {vc.name}"
        temp_vc = await guild.create_voice_channel(
            vc_name,
            category=category,
            user_limit=config.max_users,
            reason="For the temporary VC Cog.",
        )

        # Add the new VC to the temporary list for this guild

        self.temporary_vc_list[guild.id][1].append((temp_vc.id,discord.utils.utcnow()))

        return f"Created temporary voice channel: {vc_name}"

    @vc.command(name="create")
    async def create_temp_vc(self, ctx: commands.Context):
        """Command to create a temporary voice channel in the stored category with stored max users."""
        # Fetch the category and configuration from the database
        guild = ctx.guild

        if not ctx.guild:
            await ctx.send("You can only use this in a guild.")
        result=await self.create_temp_vc_2(guild)
        await ctx.send(result)

    @vc.command(name="clear")
    async def clear_unused(self, ctx: commands.Context):
        """Command to create a temporary voice channel in the stored category with stored max users."""
        # Fetch the category and configuration from the database
        guild = ctx.guild

        config = await TempVCConfig.get_temp_vc_config(guild.id)
        if not config:
            await ctx.send(
                "Temporary VC configuration is not set. Use `>serverconfig set` to set it."
            )
            return

        category = discord.utils.get(guild.categories, id=config.category_id)
        if category is None:
            await ctx.send("Category not found.")
            return
        if guild.id not in self.temporary_vc_list:
            self.temporary_vc_list[guild.id] = [0,[]]
        # Iterate through all voice channels in the category
        for vc in category.voice_channels:
            # If the channel has members, add it to the vc_list and skip deletion
            if config.name not in vc.name:
                await ctx.send(f"Skipping {vc.name} because it doesn't match {config.name}")
                continue
            if len(vc.members) > 0:
                if vc.id not in self.temporary_vc_list[guild.id][1]:

                    self.temporary_vc_list[guild.id][1].append(vc.id)
            # If the channel is empty, delete it and remove it from the temporary list
            else:
                await vc.delete(reason="Temporary VC is empty.")

                if vc.id in self.temporary_vc_list[guild.id][1]:
                    self.temporary_vc_list[guild.id][1].remove(vc.id)
        await ctx.send("Cleared all unused vcs from target category.")

    @tasks.loop(minutes=5)
    async def check_empty_vc(self):
        """Task that checks if the temporary VCs are empty and deletes them if they are."""
        for guild_id, vc_ids in list(self.temporary_vc_list.items()):
            guild = self.bot.get_guild(guild_id)
            if guild:
                for vc_id in vc_ids[1]:
                    vc = guild.get_channel(vc_id)
                    if vc and isinstance(vc, discord.VoiceChannel):
                        # Check if the planet is more than 2 minutes old
                        if (discord.utils.utcnow() - vc.created_at) < timedelta(minutes=2):
                            continue
                        # Check if the channel is empty
                        if len(vc.members) == 0:
                            await vc.delete(reason="Temporary VC is empty.")
                            self.temporary_vc_list[guild_id][1].remove(vc_id)

            # If no more VCs exist for the guild, remove the guild entry
            if not self.temporary_vc_list[guild_id][1]:
                del self.temporary_vc_list[guild_id]

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Task that checks if the temporary VCs are empty and deletes them if they are."""
        if not member.guild:
            return
        guild = member.guild
        if guild.id not in self.temporary_vc_list:
            return
        vc_ids = self.temporary_vc_list[guild.id][1]

        if guild:
            for vc_id in vc_ids[1]:
                vc = guild.get_channel(vc_id)
                if vc and isinstance(vc, discord.VoiceChannel):
                    # Check if the planet is more than 2 minutes old
                    if (discord.utils.utcnow() - vc.created_at) < timedelta(minutes=2):
                        continue
                    # Check if the channel is empty
                    if len(vc.members) == 0:
                        await vc.delete(reason="Temporary VC is empty.")
                        self.temporary_vc_list[guild.id][1].remove(vc_id)

        # If no more VCs exist for the guild, remove the guild entry
        if not self.temporary_vc_list[guild.id][1]:
            del self.temporary_vc_list[guild.id]


async def setup(bot):
    await bot.add_cog(TempVC(bot))
