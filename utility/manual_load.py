import os
import json

from discord.ext import commands, tasks
directory="./manual"

def load_json_with_substitutions(directory, filename, substitutions):
    file_path = os.path.join(directory, filename)

    # Read the JSON file as a string
    with open(file_path, 'r') as file:
        json_string = file.read()

    # Perform substitutions
    for key, value in substitutions.items():
        json_string = json_string.replace(key, value)

    # Parse the modified JSON string
    json_data = json.loads(json_string)

    return json_data



def substitute(data, substring, substitute):
    if isinstance(data, dict):
        return {key: substitute(data[key], substring, substitute) if isinstance(data[key], (dict, list)) else substitute_string(data[key], substring, substitute) for key in data}
    elif isinstance(data, list):
        return [substitute(item, substring, substitute) if isinstance(item, (dict, list)) else substitute_string(item, substring, substitute) for item in data]
    else:
        return substitute_string(data, substring, substitute)


def substitute_string(string, substring, substitute):
    return string.replace(substring, substitute)

def load_manual(file:str,ctx:commands.Context):
    subs={"$BOTID$":str(ctx.bot.user.id)}
    jsondata=load_json_with_substitutions("./manual",file,subs)
    return jsondata