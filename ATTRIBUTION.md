# Third-Party Code Attribution

This project includes algorithms ported from open-source projects for enhanced compatibility with private server GRF files.

## GRFEditor

**Source**: https://github.com/tokei/GRFEditor  
**License**: (Check original repository for license)

### Algorithms Ported

1. **LZSS Decompression**
   - **Source**: `GRF/Core/Compression.cs::LzssDecompress()`
   - **Location**: `src/extractors/grf_decompression_fallback.py::lzss_decompress()`
   - **Purpose**: Handles LZSS-compressed GRF files used by some private servers

2. **Enhanced Zlib Decompression Strategies**
   - **Source**: `GRF/Core/GrfCompression/` (multiple files)
   - **Location**: `src/extractors/grf_decompression_fallback.py::decompress_with_grfeditor_fallback()`
   - **Purpose**: Multiple fallback strategies for problematic zlib-compressed files

## ActEditor / GRFEditor (SPR Format)

**Source**: https://github.com/tokei/GRFEditor (SPR format parsing)  
**License**: (Check original repository for license)

### Algorithms Ported

1. **SPR RLE Decompression**
   - **Source**: `GRF/FileFormats/Rle.cs::Decompress()`
   - **Location**: `src/parsers/spr_parser_fallback.py::decompress_rle()`
   - **Purpose**: Proper RLE decompression for SPR version 2.1 files

2. **BGRA32 to RGBA Conversion**
   - **Source**: `GRF/FileFormats/SprFormat/SprLoader.cs::_loadBgra32Image()`
   - **Location**: `src/parsers/spr_parser_fallback.py::convert_bgra32_to_rgba()`
   - **Purpose**: Correct color channel order and Y-axis flipping for RGBA sprites

3. **Enhanced SPR Parser**
   - **Source**: `GRF/FileFormats/SprFormat/SprLoader.cs`
   - **Location**: `src/parsers/spr_parser_fallback.py::parse_spr_fallback()`
   - **Purpose**: More robust SPR parsing with better error handling

## Implementation Notes

- All algorithms have been ported from C# to Python
- Fallback parsers are used only when primary parsers fail
- Original functionality is preserved - fallbacks are additive
- No C# code or dependencies are included in the repository

## License Compliance

If the original projects have specific license requirements, they should be included here. Please check the original repositories for license details.
