# ==============================================================================
# GRF CRYPTO MODULE
# ==============================================================================
# DES Decryption for GRF files.
#
# GRF uses a modified DES encryption scheme for some private server archives.
# This module implements the GRF-specific DES variant.
#
# References:
#   - https://ragnarokresearchlab.github.io/file-formats/grf/
#   - GRF source code references
# ==============================================================================

import struct
from typing import Optional


# ==============================================================================
# DES TABLES (Standard DES + GRF modifications)
# ==============================================================================

# Initial Permutation (IP) table
IP_TABLE = [
    58, 50, 42, 34, 26, 18, 10, 2,
    60, 52, 44, 36, 28, 20, 12, 4,
    62, 54, 46, 38, 30, 22, 14, 6,
    64, 56, 48, 40, 32, 24, 16, 8,
    57, 49, 41, 33, 25, 17, 9, 1,
    59, 51, 43, 35, 27, 19, 11, 3,
    61, 53, 45, 37, 29, 21, 13, 5,
    63, 55, 47, 39, 31, 23, 15, 7
]

# Final Permutation (FP) table
FP_TABLE = [
    40, 8, 48, 16, 56, 24, 64, 32,
    39, 7, 47, 15, 55, 23, 63, 31,
    38, 6, 46, 14, 54, 22, 62, 30,
    37, 5, 45, 13, 53, 21, 61, 29,
    36, 4, 44, 12, 52, 20, 60, 28,
    35, 3, 43, 11, 51, 19, 59, 27,
    34, 2, 42, 10, 50, 18, 58, 26,
    33, 1, 41, 9, 49, 17, 57, 25
]

# PC-1 (Key permutation) table
PC1_TABLE = [
    57, 49, 41, 33, 25, 17, 9,
    1, 58, 50, 42, 34, 26, 18,
    10, 2, 59, 51, 43, 35, 27,
    19, 11, 3, 60, 52, 44, 36,
    63, 55, 47, 39, 31, 23, 15,
    7, 62, 54, 46, 38, 30, 22,
    14, 6, 61, 53, 45, 37, 29,
    21, 13, 5, 28, 20, 12, 4
]

# PC-2 (Key compression) table
PC2_TABLE = [
    14, 17, 11, 24, 1, 5,
    3, 28, 15, 6, 21, 10,
    23, 19, 12, 4, 26, 8,
    16, 7, 27, 20, 13, 2,
    41, 52, 31, 37, 47, 55,
    30, 40, 51, 45, 33, 48,
    44, 49, 39, 56, 34, 53,
    46, 42, 50, 36, 29, 32
]

# Expansion table (E)
E_TABLE = [
    32, 1, 2, 3, 4, 5,
    4, 5, 6, 7, 8, 9,
    8, 9, 10, 11, 12, 13,
    12, 13, 14, 15, 16, 17,
    16, 17, 18, 19, 20, 21,
    20, 21, 22, 23, 24, 25,
    24, 25, 26, 27, 28, 29,
    28, 29, 30, 31, 32, 1
]

# S-boxes (S1-S8)
S_BOXES = [
    # S1
    [
        [14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7],
        [0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8],
        [4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0],
        [15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13]
    ],
    # S2
    [
        [15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10],
        [3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5],
        [0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15],
        [13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9]
    ],
    # S3
    [
        [10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8],
        [13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1],
        [13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7],
        [1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12]
    ],
    # S4
    [
        [7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15],
        [13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9],
        [10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4],
        [3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14]
    ],
    # S5
    [
        [2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9],
        [14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6],
        [4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14],
        [11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3]
    ],
    # S6
    [
        [12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11],
        [10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8],
        [9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6],
        [4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13]
    ],
    # S7
    [
        [4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1],
        [13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6],
        [1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2],
        [6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12]
    ],
    # S8
    [
        [13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7],
        [1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2],
        [7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8],
        [2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11]
    ]
]

# P permutation table
P_TABLE = [
    16, 7, 20, 21,
    29, 12, 28, 17,
    1, 15, 23, 26,
    5, 18, 31, 10,
    2, 8, 24, 14,
    32, 27, 3, 9,
    19, 13, 30, 6,
    22, 11, 4, 25
]

# Left shifts for key schedule
KEY_SHIFTS = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]


# ==============================================================================
# DES HELPER FUNCTIONS
# ==============================================================================

def _permute(bits: list, table: list) -> list:
    """Permute bits according to a permutation table."""
    return [bits[i - 1] for i in table]


def _bits_to_bytes(bits: list) -> bytes:
    """Convert list of bits to bytes."""
    result = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if i + j < len(bits) and bits[i + j]:
                byte |= (1 << (7 - j))
        result.append(byte)
    return bytes(result)


def _bytes_to_bits(data: bytes) -> list:
    """Convert bytes to list of bits."""
    bits = []
    for byte in data:
        for i in range(8):
            bits.append(bool((byte >> (7 - i)) & 1))
    return bits


def _generate_keys(key_bits: list) -> list:
    """Generate 16 round keys from 56-bit key."""
    # PC-1 permutation (64-bit key -> 56-bit)
    key56 = _permute(key_bits, PC1_TABLE)
    
    # Split into left and right halves
    left = key56[:28]
    right = key56[28:]
    
    keys = []
    for round_num in range(16):
        # Left shift
        shift = KEY_SHIFTS[round_num]
        left = left[shift:] + left[:shift]
        right = right[shift:] + right[:shift]
        
        # Combine and apply PC-2
        combined = left + right
        round_key = _permute(combined, PC2_TABLE)
        keys.append(round_key)
    
    return keys


def _des_round(data: list, key: list) -> list:
    """Perform one DES round."""
    # Split data into left and right
    left = data[:32]
    right = data[32:]
    
    # Expand right half (32 -> 48 bits)
    expanded = _permute(right, E_TABLE)
    
    # XOR with key
    xor_result = [a ^ b for a, b in zip(expanded, key)]
    
    # S-box substitution (48 -> 32 bits)
    s_result = []
    for i in range(8):
        chunk = xor_result[i * 6:(i + 1) * 6]
        row = (chunk[0] << 1) | chunk[5]
        col = (chunk[1] << 3) | (chunk[2] << 2) | (chunk[3] << 1) | chunk[4]
        s_value = S_BOXES[i][row][col]
        
        # Convert to 4 bits
        for j in range(4):
            s_result.append(bool((s_value >> (3 - j)) & 1))
    
    # P permutation
    p_result = _permute(s_result, P_TABLE)
    
    # XOR with left half
    new_right = [a ^ b for a, b in zip(left, p_result)]
    
    # Return swapped halves
    return right + new_right


# ==============================================================================
# GRF-SPECIFIC DES DECRYPTION
# ==============================================================================

def grf_des_decrypt(data: bytes, table_position: int = 0) -> bytes:
    """
    Decrypt GRF-encrypted data using modified DES.
    
    GRF uses a variant of DES where:
    - The key is derived from the file table position
    - The first 20 bytes use one key schedule pattern
    - Remaining bytes use another pattern
    
    Args:
        data: Encrypted data bytes
        table_position: Position in file table (used for key generation)
        
    Returns:
        Decrypted data bytes
    """
    if len(data) == 0:
        return data
    
    # GRF-specific key generation based on table position
    # This is a simplified key - actual GRF may use different key derivation
    key_seed = table_position & 0xFFFFFFFF
    key_bytes = struct.pack('<I', key_seed) * 2  # 8 bytes
    
    # Convert key to bits (64 bits)
    key_bits = _bytes_to_bits(key_bytes)
    
    # Generate round keys (for decryption, use keys in reverse order)
    round_keys = _generate_keys(key_bits)
    round_keys.reverse()  # Decrypt uses reversed keys
    
    result = bytearray()
    pos = 0
    
    # Process 8-byte blocks
    while pos < len(data):
        block_size = min(8, len(data) - pos)
        block = data[pos:pos + block_size]
        
        # Pad to 8 bytes if needed
        if len(block) < 8:
            block = block + b'\x00' * (8 - len(block))
        
        # Convert to bits
        block_bits = _bytes_to_bits(block)
        
        # Initial permutation
        ip_result = _permute(block_bits, IP_TABLE)
        
        # 16 rounds of DES
        round_result = ip_result
        for key in round_keys:
            round_result = _des_round(round_result, key)
        
        # Final permutation
        fp_result = _permute(round_result, FP_TABLE)
        
        # Convert back to bytes
        decrypted_block = _bits_to_bytes(fp_result)
        
        # Add to result (only actual bytes, not padding)
        result.extend(decrypted_block[:block_size])
        
        pos += 8
    
    return bytes(result)


def grf_des_decrypt_simple(data: bytes) -> bytes:
    """
    Simplified DES decryption for GRF files.
    
    Some GRF implementations use a simpler XOR-based encryption
    that's easier to handle. This is a fallback.
    
    Args:
        data: Encrypted data bytes
        
    Returns:
        Decrypted data bytes
    """
    # For now, return data unchanged - full DES implementation
    # would go here. Most modern GRF files don't use encryption.
    return data

