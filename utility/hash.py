import hashlib

def get_hash_sets():
    '''get a list of all hashsets'''
    list=[i for i, v in hashsets.items()]
    return list

hashsets={
    'alphanumeric':"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    'alphanumeric_upper':'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    'alphanumeric_lower':'abcdefghijklmnopqrstuvwxyz0123456789',
    'numeric':'0123456789',
    'hex':'0123456789abcdef',
    'b64':"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/",
    'b32':"0123456789bcdefghjklmnpqrstvwxyz",
    'default':"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789%-"


}
def hash_string(string_to_hash, hashlen=5, hashset='default'):
    'hash a string'
    # Convert the string to bytes
    encoded_string = string_to_hash.encode('utf-8')
    # Hash the bytes using SHA-256
    hash_bytes = hashlib.sha256(encoded_string).digest()

    char_set = hashsets[hashset] #
    base_len = len(char_set)
    num_chars = hashlen
    num_bits = num_chars * 6
    hash_int = int.from_bytes(hash_bytes, byteorder='big')
    chars = []
    for i in range(num_chars):
        offset = i * 6
        index = (hash_int >> offset) & 0x3f
        chars.append(char_set[index%base_len])
    encoded_chars = ''.join(chars)

    return encoded_chars,hash_int