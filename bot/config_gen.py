import configparser
import os
from pathlib import Path
import gui
from .TauCetiBot import TCBot, ConfigParserSub

import keyring
import sys
import trace
import nacl.secret
import nacl.utils
import nacl.exceptions
import base64

from .key_vault import keyring_setup, print_package

default_config = {
    # The default configuration.
    "archive": {"max_lazy_archive_minutes": 10},
    "optional": {"error_channel_id": None, "feedback_channel_id": None},
    "feature": {"playwright": True, "gui": True},
}


def setup(args):
    "get or create the config.ini file."
    arglength = len(args)
    keys = ConfigParserSub()
    config = ConfigParserSub()
    c1 = c2 = True
    if not os.path.exists("config.ini"):
        gui.gprint("No config.ini file detected.")
        c1 = False
    if not os.path.exists("keys.ini"):
        gui.gprint("No keys.ini file detected.")
        c2 = False
    if not os.path.exists("config.ini") or not os.path.exists("keys.ini"):
        if c1 and not c2:
            config.read("config.ini")
            gui.gprint("config.ini found but no keys.ini")
            for section in config.sections():
                if section in ["vital", "optional"]:
                    keys.add_section(section)
                    for option in config.options(section):
                        if option != "error_channel_id":
                            value = config.get(section, option)
                            keys.set(section, option, value)
                            config.remove_option(section, option)
            config.write(open("config.ini", "w+"))
            keys.write(open("keys.ini", "w+"))
        else:
            botname, token, error_channel_id = "", "", ""
            if arglength > 1:
                botname = args[1]
            if arglength > 2:
                token = args[2]
            if arglength > 3:
                error_channel_id = args[3]
            if not botname:
                botname = input(
                    "Please enter your bot's name (this can not be changed.): "
                )
            if not token:
                token = input("Please enter your bot token: ")
            if not error_channel_id:
                error_channel_id = input(
                    "Please enter the ID of the channel to send error messages to, or 'NEWGUILD': "
                )

            keys["vital"] = {"botname": botname}
            keyring.set_password("bot_service", botname, token)
            keys["vital"] = {"cipher": token}
            config["optional"] = {"error_channel_id": error_channel_id}
            gui.gprint("Writing config files")
            config.write(open("config.ini", "w"))
            keys.write(open("keys.ini", "w+"))
        try:
            gui.gprint("making savedata")
            Path("/saveData").mkdir(parents=True, exist_ok=True)  # saveData
        except FileExistsError:
            gui.gprint("saveData exists already.")
        try:
            gui.gprint("making logs")
            Path("/logs").mkdir(parents=True, exist_ok=True)  # logs
        except FileExistsError:
            gui.gprint("logs exists already.")
        gui.gprint("you can restart the bot now.")

        return None, None

    else:
        # Read File.
        print_package()
        keys.read("keys.ini")
        config.read("config.ini")
        if config.get("vital", "cipher", fallback=None) != None:
            gui.gprint("Bot token detected in config.ini!  Transferring to keys.ini")
            for section in config.sections():
                keys.add_section(section)
                for option in config.options(section):
                    if option != "error_channel_id":
                        value = config.get(section, option)
                        keys.set(section, option, value)
                        config.remove_option(section, option)
            config.write(open("config.ini", "w+"))
            keys.write(open("keys.ini", "w+"))
        keys = keyring_setup(keys)

        return config, keys


def config_update(config):
    changes = False
    for section_name, dictionary in default_config.items():
        if not config.has_section(section_name):
            config.add_section(section_name)
        for key, value in dictionary.items():
            # Check if the key exists in the config file
            if not config.has_option(section_name, key):
                # Add the key-value pair to the config file
                config.set(section_name, key, str(value))
                changes = True
    if changes:
        config.write(open("config.ini", "w+"))
