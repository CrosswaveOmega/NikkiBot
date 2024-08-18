import os
import json

from discord.ext import commands, tasks

directory = "./manual"


def load_json_with_substitutions(directory: str, filename: str, substitutions: dict):
    """
    Load a JSON file from the given directory, apply any substitutuions to the
    JSON string contained within the substitutions dictionary, and load in a
    dictionary from the result.

    Args:
        directory (str): The directory where the JSON file is located.
        filename (str): The name of the JSON file.
        substitutions (dict): A dictionary containing any substitutions to be applied.

    Returns:
        dict: The parsed JSON data with substitutions applied.
    """
    file_path = os.path.join(directory, filename)

    # Read the JSON file as a string
    with open(file_path, "r", encoding="utf-8") as file:
        json_string = file.read()

    # Perform substitutions
    if substitutions:
        for key, value in substitutions.items():
            json_string = json_string.replace(key, value)

    # Parse the modified JSON string
    json_data = json.loads(json_string)

    return json_data


def load_manual(file: str, ctx: commands.Context):
    bot: commands.Bot = ctx.bot
    subs = {"$BOTID$": str(bot.user.id), "$APPNAME$": str(bot.application.name)}
    jsondata = load_json_with_substitutions("./manual", file, subs)
    return jsondata
