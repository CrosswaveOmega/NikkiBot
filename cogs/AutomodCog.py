import gui
import discord

# import datetime
from datetime import timedelta


from discord.ext import commands

from discord import app_commands
from bot import TC_Cog_Mixin


from discord import (
    AutoModRule,
    AutoModAction,
    AutoModTrigger,
    AutoModRuleTriggerType,
    AutoModRuleAction,
)


class AutomodCog(commands.Cog, TC_Cog_Mixin):
    """This cog is a placeholder for future automod commands."""

    def __init__(self, bot):
        self.helptext = ""
        self.bot = bot

    @commands.Cog.listener()
    async def on_automod_rule_create(self, rule: AutoModRule):
        gui.print(rule)
        pass

    @commands.Cog.listener()
    async def on_automod_rule_update(self, rule: AutoModRule):
        gui.print(rule)
        pass

    @commands.Cog.listener()
    async def on_automod_rule_delete(self, rule: AutoModRule):
        gui.print(rule)
        pass

    @commands.Cog.listener()
    async def on_automod_action(self, execution: AutoModAction):
        gui.print(execution)
        pass

    @app_commands.command(
        name="automodadd",
        description="this command adds in an automod rule that prevents invites.",
    )
    @app_commands.describe(
        modchannel="The moderation channel to be notified of this rule in."
    )
    @app_commands.checks.bot_has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def automod(
        self, interaction: discord.Interaction, modchannel: discord.TextChannel
    ) -> None:
        """"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild = ctx.guild
        rulename = "No invite posting"
        """
        valid automod trigger types
        keyword: The rule will trigger when a keyword is mentioned.

        harmful_link:The rule will trigger when a harmful link is posted.

        spam: The rule will trigger when a spam message is posted.

        keyword_preset: The rule will trigger when something triggers based on the set keyword preset types.

        mention_spam: The rule will trigger when combined number of role and user mentions is greater than the set limit.
        """
        amtrigger: AutoModTrigger = AutoModTrigger(
            type=AutoModRuleTriggerType.keyword,
            regex_patterns=[
                "(?:https?://)?discord(?:app)?\.(?:com/invite|gg)/[a-zA-Z0-9]+/?"
            ],
            keyword_filter=["invite"],
        )
        actiona = AutoModRuleAction(
            custom_message="Invite links are against the rules here!"
        )
        actionb = AutoModRuleAction(channel_id=modchannel.id)
        actionc = AutoModRuleAction(duration=timedelta(hours=3))
        # creating an automod rule
        await guild.create_automod_rule(
            # The name of the automodrule
            name=rulename,
            # the event type, although the only type right now is
            # on message send.
            event_type=discord.AutoModRuleEventType.message_send,
            # The trigger for the automod rule.  see above for an example.
            trigger=amtrigger,
            # A list of actions to take
            actions=[actiona, actionb],
            enabled=True,
            # What channels should be exempt from the automod rule?
            exempt_channels=[modchannel],
            # What roles are exempt from the automod rule?
            exempt_roles=[],
            # add a reason for the audit logs
            reason="To experiment with the automod.",
        )
        await ctx.send(f"Automod rule {rulename} created.")


async def setup(bot):
    await bot.add_cog(AutomodCog(bot))
