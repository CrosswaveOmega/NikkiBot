import discord
from discord.ext import commands
from utility import formatutil

"""print out a new error message."""


def client_error_message(error_main, name="command"):
    error = error_main

    if isinstance(error, commands.HybridCommandError):
        error = error.original
    if isinstance(error, discord.ext.commands.errors.CommandNotFound):
        return f"`{name}` is not a valid command, sorry."
    if isinstance(error, discord.app_commands.BotMissingPermissions) or isinstance(
        error, commands.BotMissingPermissions
    ):
        # Handle the specific error

        missing = formatutil.permission_print(error.missing_permissions)
        missing += " permission"
        if len(error.missing_permissions) > 1:
            missing += "s"
        return f"I'm sorry, but I can not invoke {name} without the {missing}."
    if isinstance(error,discord.ext.commands.errors.CheckFailure):
        return f"{name} failed a check."
    else:
        return f"{name} failed due to {str(error)}"
