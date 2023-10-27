import hashlib
import discord
from enum import Enum


class Hashsets(Enum):
    """
    Enumeration of character sets for generating hash values.

    Attributes:
        default (int): Represents the default character set, has 64 chars.
        alphanumeric (int): Represents the set of alphanumeric characters, 62 chars.
        numeric (int): Represents the set of numeric characters from 0-9, has 10 chars
        decimal (int): Represents the set of decimal characters from 0-9(equivalent to `numeric`).
        alphanumeric_upper (int): Represents the set of uppercase alphanumeric characters, 36 chars.
        alphanumeric_lower (int): Represents the set of lowercase alphanumeric characters, 36 chars.
        base32 (int): Represents the Base32 character set, 32 chars.
        base64 (int): Represents the Base64 character set, 64 chars.
        hex (int): Represents the hexadecimal character set, 16 chars.
    """

    default = 0
    alphanumeric = 1
    numeric = 2
    decimal = 2
    alphanumeric_upper = 3
    alphanumeric_lower = 4
    base32 = 5
    base64 = 6
    hex = 7

    def __str__(self) -> str:
        return self.name


def get_hash_sets():
    """get a list of all hashsets"""
    list = [i for i, v in hashsets.items()]
    return list


hashsets = {
    "alphanumeric": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "alphanumeric_upper": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "alphanumeric_lower": "abcdefghijklmnopqrstuvwxyz0123456789",
    "numeric": "0123456789",
    "hex": "0123456789abcdef",
    "base64": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/",
    "base32": "0123456789bcdefghjklmnpqrstvwxyz",
    "default": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789%-",
}


def hash_string(string_to_hash, hashlen=5, hashset: Hashsets = Hashsets.default):
    """Given a string, generate a string representation of a hash ."""
    # Convert the string to bytes
    encoded_string = string_to_hash.encode("utf-8")
    # Hash the bytes using SHA-256
    hash_bytes = hashlib.sha256(encoded_string).digest()

    char_set = hashsets[str(hashset)]  #
    base_len = len(char_set)
    num_chars = hashlen
    num_bits = num_chars * 6
    hash_int = int.from_bytes(hash_bytes, byteorder="big")
    chars = []
    for i in range(num_chars):
        offset = i * 6
        index = (hash_int >> offset) & 0x3F
        chars.append(char_set[index % base_len])
    encoded_chars = "".join(chars)

    return encoded_chars, hash_int
