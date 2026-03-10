
# arm256_with_aes.py
# Integrated from user's arm256_per_tx_blockchain implementation
import time, json, math, struct, base64, threading
from typing import List, Dict, Any, Optional
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

# -------------------------
# ARM256 (custom) hash
# -------------------------
# TO — pre-computed, instant
PRIMES = [2,3,5,7,11,13,17,19]
PLANCK = 6.62607015
H_INIT = [0x6a4b8f2e, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
          0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
K_INIT = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
          0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5]

def _rotr(x: int, n: int) -> int:
    return ((x >> n) | ((x << (32 - n)) & 0xFFFFFFFF)) & 0xFFFFFFFF

# FIXED — actual bytes
def pad_message(m: bytes) -> bytes:
    ml = len(m) * 8
    m += b'\x80'         # ← single byte 0x80
    while (len(m) * 8) % 512 != 448:
        m += b'\x00'     # ← single byte 0x00
    m += struct.pack('>Q', ml)
    return m



def arm256_hexdigest(message: str) -> str:
    m = pad_message(message.encode('utf-8'))
    H = H_INIT.copy()
    K = K_INIT.copy()
    for i in range(0, len(m), 64):
        block = m[i:i+64]
        w = list(struct.unpack('>16I', block))
        for t in range(16,64):
            s0 = _rotr(w[t-15],7) ^ _rotr(w[t-15],18) ^ (w[t-15]>>3)
            s1 = _rotr(w[t-2],17) ^ _rotr(w[t-2],19) ^ (w[t-2]>>10)
            w.append((w[t-16] + s0 + w[t-7] + s1) & 0xFFFFFFFF)
        a,b,c,d,e,f,g,h = H
        for t in range(64):
            T1 = (h + (_rotr(e,6)^_rotr(e,11)^_rotr(e,25)) + ((e&f) ^ (~e & g)) + K[t % len(K)] + w[t]) & 0xFFFFFFFF
            T2 = ((_rotr(a,2)^_rotr(a,13)^_rotr(a,22)) + ((a&b) ^ (a&c) ^ (b&c))) & 0xFFFFFFFF
            h = g; g = f; f = e; e = (d + T1) & 0xFFFFFFFF
            d = c; c = b; b = a; a = (T1 + T2) & 0xFFFFFFFF
        H = [ (H[i] + v) & 0xFFFFFFFF for i,v in enumerate([a,b,c,d,e,f,g,h]) ]
    return ''.join(f'{x:08x}' for x in H)

# -------------------------
# AES-GCM encryption/decryption helpers
# -------------------------
PBKDF2_ITERATIONS = 200_000
KEY_LEN = 32
SALT_LEN = 16
NONCE_LEN = 12
TAG_LEN = 16

def _derive_key(password: str, salt: bytes) -> bytes:
    return PBKDF2(password.encode('utf-8'), salt, dkLen=KEY_LEN, count=PBKDF2_ITERATIONS)

def encrypt_text_with_salt(plaintext: str, password: str, salt: bytes) -> str:
    key = _derive_key(password, salt)
    nonce = get_random_bytes(NONCE_LEN)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))
    packed = salt + nonce + tag + ciphertext
    return base64.b64encode(packed).decode('utf-8')

def decrypt_text_with_salt(b64_input: str, password: str) -> str:
    data = base64.b64decode(b64_input)
    if len(data) < SALT_LEN + NONCE_LEN + TAG_LEN:
        raise ValueError("Input too short or corrupt")
    salt = data[:SALT_LEN]
    nonce = data[SALT_LEN:SALT_LEN+NONCE_LEN]
    tag = data[SALT_LEN+NONCE_LEN:SALT_LEN+NONCE_LEN+TAG_LEN]
    ciphertext = data[SALT_LEN+NONCE_LEN+TAG_LEN:]
    key = _derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    pt = cipher.decrypt_and_verify(ciphertext, tag)
    return pt.decode('utf-8')

# Compatibility wrappers expected by the app
def encrypt_text(plaintext: str, password: str) -> str:
    """Return base64 string containing salt+nonce+tag+ciphertext"""
    salt = get_random_bytes(SALT_LEN)
    return encrypt_text_with_salt(plaintext, password, salt)

def decrypt_text(b64_input: str, password: str) -> str:
    """Decrypt data produced by encrypt_text"""
    return decrypt_text_with_salt(b64_input, password)
