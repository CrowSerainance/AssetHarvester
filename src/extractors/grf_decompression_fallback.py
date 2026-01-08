# ==============================================================================
# GRF DECOMPRESSION FALLBACK MODULE
# ==============================================================================
# Fallback decompression strategies ported from GRFEditor.
# 
# This module provides enhanced decompression algorithms that handle edge cases
# and private server GRF variations that the primary parser may not support.
#
# Ported from GRFEditor (https://github.com/tokei/GRFEditor):
#   - LZSS decompression: GRF/Core/Compression.cs::LzssDecompress()
#   - Enhanced zlib strategies: GRF/Core/GrfCompression/
#
# Usage:
#   from src.extractors.grf_decompression_fallback import decompress_with_fallback
#   data = decompress_with_fallback(compressed_data, uncompressed_size, compression_type)
# ==============================================================================

import zlib
import struct
from typing import Optional


def lzss_decompress(compressed_data: bytes, uncompressed_length: int) -> Optional[bytes]:
    """
    Decompress LZSS-compressed data.
    
    Ported from GRFEditor GRF/Core/Compression.cs::LzssDecompress()
    
    LZSS (Lempel-Ziv-Storer-Szymanski) is a variant of LZ77 compression used
    in some GRF files, particularly older or private server variants.
    
    Algorithm:
    - Control byte determines if next byte is literal or reference
    - Literal: Copy byte directly
    - Reference: Copy from previous position (codeword format)
    
    Args:
        compressed_data: LZSS-compressed data
        uncompressed_length: Expected decompressed size
        
    Returns:
        Decompressed data, or None on error
    """
    if not compressed_data or uncompressed_length == 0:
        return b""
    
    if uncompressed_length < 0:
        return None
    
    try:
        output = bytearray(uncompressed_length)
        output_offset = 0
        input_offset = 0
        input_length = len(compressed_data)
        
        if input_offset >= input_length:
            return None
        
        # Read control byte
        control = compressed_data[input_offset]
        input_offset += 1
        control_count = 0
        
        while input_offset < input_length and output_offset < uncompressed_length:
            if (control & 1) == 0:
                # Literal: copy byte directly
                if input_offset >= input_length:
                    break
                if output_offset >= uncompressed_length:
                    break
                output[output_offset] = compressed_data[input_offset]
                output_offset += 1
                input_offset += 1
            else:
                # Reference: copy from previous position
                if input_offset + 1 >= input_length:
                    break
                
                # Read codeword (2 bytes, little-endian)
                codeword = struct.unpack('<H', compressed_data[input_offset:input_offset + 2])[0]
                input_offset += 2
                
                # Extract phrase length and index from codeword
                phrase_length = ((codeword & 0xf000) >> 12) + 2
                phrase_index = codeword & 0x0fff
                
                # Validate phrase_index
                if phrase_index == 0 or phrase_index > output_offset:
                    # Invalid reference - might be corrupted
                    return None
                
                # Copy phrase from previous position
                for i in range(phrase_length):
                    if output_offset >= uncompressed_length:
                        break
                    if output_offset - phrase_index < 0:
                        return None  # Invalid reference
                    output[output_offset] = output[output_offset - phrase_index]
                    output_offset += 1
            
            # Shift control byte and check if we need a new one
            control = control >> 1
            control_count += 1
            
            if control_count >= 8:
                if input_offset >= input_length:
                    break
                control = compressed_data[input_offset]
                input_offset += 1
                control_count = 0
        
        # Validate we decompressed the expected amount
        if output_offset < uncompressed_length * 0.9:  # Allow 10% tolerance
            return None
        
        return bytes(output[:output_offset])
        
    except (struct.error, IndexError, ValueError) as e:
        # Silently fail - invalid LZSS data
        return None
    except Exception as e:
        return None


def decompress_with_grfeditor_fallback(
    compressed_data: bytes,
    uncompressed_size: int,
    compression_type: int = 1
) -> Optional[bytes]:
    """
    Decompress GRF file data using GRFEditor fallback strategies.
    
    This function tries multiple decompression methods in order:
    1. Standard zlib
    2. Raw deflate (no header)
    3. LZSS decompression
    4. LZMA decompression (if available)
    5. Uncompressed data check
    
    Args:
        compressed_data: Compressed file data
        uncompressed_size: Expected uncompressed size
        compression_type: Compression type from GRF entry (0=raw, 1=zlib, 2=DES+zlib, 3=DES, 4=LZMA)
        
    Returns:
        Decompressed data, or None if all strategies fail
    """
    if not compressed_data:
        return None
    
    # Type 0: Raw/uncompressed
    if compression_type == 0:
        if len(compressed_data) == uncompressed_size:
            return compressed_data
        return None
    
    # Type 1: Zlib (try multiple strategies)
    if compression_type == 1:
        # Strategy 1: Standard zlib
        try:
            decompressed = zlib.decompress(compressed_data)
            if uncompressed_size == 0 or abs(len(decompressed) - uncompressed_size) <= uncompressed_size * 0.2:
                return decompressed
        except zlib.error:
            pass
        
        # Strategy 2: Raw deflate (no zlib header)
        try:
            decompressed = zlib.decompress(compressed_data, -zlib.MAX_WBITS)
            if uncompressed_size == 0 or abs(len(decompressed) - uncompressed_size) <= uncompressed_size * 0.2:
                return decompressed
        except zlib.error:
            pass
        
        # Strategy 3: Try different window sizes
        for wbits in [15, -15, 31, 47]:
            try:
                decompressed = zlib.decompress(compressed_data, wbits)
                if uncompressed_size == 0 or abs(len(decompressed) - uncompressed_size) <= uncompressed_size * 0.2:
                    return decompressed
            except zlib.error:
                continue
        
        # Strategy 4: Skip first 2 bytes (custom header)
        if len(compressed_data) > 2:
            try:
                decompressed = zlib.decompress(compressed_data[2:])
                if uncompressed_size == 0 or abs(len(decompressed) - uncompressed_size) <= uncompressed_size * 0.2:
                    return decompressed
            except zlib.error:
                pass
            try:
                decompressed = zlib.decompress(compressed_data[2:], -zlib.MAX_WBITS)
                if uncompressed_size == 0 or abs(len(decompressed) - uncompressed_size) <= uncompressed_size * 0.2:
                    return decompressed
            except zlib.error:
                pass
        
        # Strategy 5: Try LZSS (some files are mislabeled as zlib)
        if uncompressed_size > 0:
            lzss_result = lzss_decompress(compressed_data, uncompressed_size)
            if lzss_result:
                return lzss_result
        
        # Strategy 6: Check if data is actually uncompressed
        size_ratio = len(compressed_data) / uncompressed_size if uncompressed_size > 0 else 0
        if 0.8 <= size_ratio <= 1.2:
            return compressed_data
        
        return None
    
    # Type 4: LZMA
    if compression_type == 4:
        try:
            import lzma
            decompressed = lzma.decompress(compressed_data)
            if uncompressed_size == 0 or abs(len(decompressed) - uncompressed_size) <= uncompressed_size * 0.2:
                return decompressed
        except (ImportError, lzma.LZMAError):
            pass
        return None
    
    # Types 2 and 3 require DES decryption first (handled by caller)
    # This fallback only handles decompression after decryption
    
    return None
