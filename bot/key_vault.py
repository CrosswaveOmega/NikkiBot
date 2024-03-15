"""
Experimental secure key storage.
"""

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
from typing import List


def print_package():
    print(f"__package__ is {__package__}")


#
def get_or_generate_key(botname: str, regenerate: bool = False):
    """Get the current options key, or generate a new one."""
    option_name = f"{botname}_optionkey"
    oldkey = keyring.get_password("bot_service", option_name)
    try:
        oldkey = base64.b64decode(oldkey)
        olddec = nacl.secret.SecretBox(oldkey)
    except Exception as e:
        print(e)
        oldkey = None
    if oldkey is None or regenerate:
        print("No key found. Generating a new key.")
        generated_key = nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)
        thiskey = base64.b64encode(generated_key).decode("utf-8")
        keyring.set_password("bot_service", option_name, thiskey)
        return oldkey, base64.b64decode(thiskey)
    return oldkey, oldkey


def encrypt_data(key, data):
    cipher = nacl.secret.SecretBox(key)
    encrypted_data = cipher.encrypt(data)
    return encrypted_data


def decrypt_data(key, encrypted_data):
    cipher = nacl.secret.SecretBox(key)
    decrypted_data = cipher.decrypt(encrypted_data)
    return decrypted_data


def parse_ini_data(data):
    config = ConfigParserSub()
    config.read_string(data.decode())
    return config


def read_encryptedfile(filename, key):
    # Read encrypted data to memory
    with open(filename, "rb") as file:
        encrypted_data = file.read()
    # Decrypt data into memory
    dec = decrypt_data(key, encrypted_data)
    # return the parced data.
    return parse_ini_data(dec)


def write_encryptedfile(parsed_config, key, output_file):
    # Convert parsed config to string
    config_str = ""
    for section in parsed_config.sections():
        config_str += f"[{section}]\n"
        for k, value in parsed_config.items(section):
            config_str += f"{k} = {value}\n"

    # Encrypt the configuration string
    encrypted_config = encrypt_data(key, config_str.encode())

    # Write the encrypted data to a file
    with open(output_file, "wb") as file:
        file.write(encrypted_config)


def file_checker(filenames: List[str]):
    def decorator(func):
        def wrapper(*args, **kwargs):
            caller_frame = sys._getframe(1)
            caller_filename = caller_frame.f_globals["__file__"]
            print(caller_filename)
            caller_filename = os.path.basename(caller_filename)
            if caller_filename in filenames:
                return func(*args, **kwargs)
            else:
                raise PermissionError(
                    f"Function '{func.__name__}' can only be called from a valid filename."
                )

        return wrapper

    return decorator


@file_checker(["bot_setup.py", "bot_main.py"])
def get_token(keys, name="botname"):
    token = keyring.get_password("bot_service", keys.get("vital", name))
    return token


def keyring_setup(keys: ConfigParserSub):
    """
    Keys.ini is used to load new keys into the secure keys file.
    Any API keys in keys.ini will be replaced with PRESENT,
    while the bot's token is replaced with TOKENLOADED.
    Replace TOKENLOADED with a new bot token to change the bot token.
    Replace PRESENT with a new api key to change that particular
    API Key.
    Set an API key to REMOVE to remove it from the optional key vault.
    """
    skey_file = "securekeys.keybox"
    token = keys.get("vital", "cipher", fallback="TOKENLOADED")
    botname = keys.get("vital", "botname", fallback=None)
    changes = False
    if token != "TOKENLOADED":
        gui.gprint("Bot token detected in Cipher!  Transferring to lockup!")
        if botname is None:
            botname = input("Please enter your bot's name (this can not be changed): ")
            keys["vital"] = {"botname": botname}
        keyring.set_password("bot_service", botname, token)
        keys.set("vital", "cipher", "TOKENLOADED")
        with open("keys.ini", "w+") as file:
            keys.write(file)
    secure_keys = ConfigParserSub()
    old_key, new_key = get_or_generate_key(botname)

    if os.path.exists(skey_file):
        secure_keys = read_encryptedfile(skey_file, old_key)

    for section in keys.sections():
        if not secure_keys.has_section(section):
            secure_keys.add_section(section)
        for k, value in keys.items(section):
            # Check if the key exists in the config file
            print(section, k, value)
            if not secure_keys.has_option(section, k):
                secure_keys.set(section, k, str(value))
                changes = True
            # INSERT/OVERRIDE OPERATIONS.
            current = secure_keys.get(section, k, fallback=None)
            if section == "optional":
                if section == "optional" and value != "PRESENT":
                    secure_keys.set(section, k, str(value))
                    keys.set(section, k, "PRESENT")
                    changes = True
                elif value == "REMOVE" and current != None:
                    secure_keys.remove_option(section, k)
                    keys.remove_option(section, k)
                    changes = True
    for section in secure_keys.sections():
        for k, value in secure_keys.items(section):
            # output old section, k, value for verification.
            pass
    if changes:
        with open("keys.ini", "w+") as file:
            keys.write(file)
        write_encryptedfile(secure_keys, new_key, skey_file)
    return secure_keys
