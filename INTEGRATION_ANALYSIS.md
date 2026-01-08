# GRFEditor/ActEditor Integration Analysis

## Overview
This document maps core parsing/rendering modules from GRFEditor and ActEditor (C#) to the current Python codebase, identifying integration points for fallback parsers.

---

## 1. GRF Parsing/Decompression Mapping

### Current Implementation
- **Location**: `src/extractors/grf_extractor.py`, `src/extractors/grf_vfs.py`
- **Current Features**:
  - Basic zlib decompression with fallback strategies
  - DES encryption placeholder (not fully implemented)
  - Multiple zlib window size attempts
  - Size validation with tolerance

### GRFEditor Implementation (C#)
- **Key Files**:
  - `GRF/Core/Compression.cs` - Multiple compression strategies
  - `GRF/Core/Encryption.cs` - DES encryption via DLL
  - `GRF/Core/GrfCompression/CpsCompression.cs` - Gravity's official zlib DLL
  - `GRF/Core/GrfCompression/LzmaCompression.cs` - LZMA support
  - `GRF/Core/GrfCompression/RecoveryCompression.cs` - Recovery mode

### Key Algorithms to Port

#### 1.1 CpsCompression (Gravity's Official Zlib)
- Uses native DLL (`cps.dll` or `comp_x64.dll`)
- **Python Alternative**: Use `zlib` with specific window bits (-15 for raw deflate)
- **Integration Point**: `src/extractors/grf_vfs.py::_decompress_zlib_multiple_strategies()`

#### 1.2 LZSS Decompression
```csharp
public static byte[] LzssDecompress(byte[] arrCompressed, long uncompressedLength)
```
- **Algorithm**: LZSS (Lempel-Ziv-Storer-Szymanski) variant
- **Integration Point**: Add as new strategy in `_decompress_file()`

#### 1.3 Multiple Compression Strategies
GRFEditor tries in order:
1. CpsCompression (Gravity DLL)
2. DotNetCompression (standard zlib)
3. LzmaCompression
4. RecoveryCompression

**Integration Strategy**: Add as fallback chain in `grf_vfs.py`

---

## 2. ACT/SPR Parsing and Rendering Mapping

### Current Implementation
- **SPR**: `src/parsers/spr_parser.py`
- **ACT**: `src/parsers/act_parser.py`
- **Preview**: `src/gui/grf_browser.py::_preview_spr()`, `_preview_act()`

### ActEditor Implementation (C#)
- **Key Files**:
  - `GRF/FileFormats/SprFormat/SprLoader.cs` - SPR loading with RLE
  - `GRF/FileFormats/ActFormat/Act.cs` - ACT parsing
  - `ActEditor/Core/SpriteManager.cs` - Sprite management
  - `ActEditor/Core/IFrameRenderer.cs` - Frame rendering interface

### Key Algorithms to Port

#### 2.1 SPR RLE Decompression
```csharp
protected void _readAsIndexed8(List<Rle> rleImages, IBinaryReader reader)
```
- **Version 2.1**: Uses RLE compression (variable frame data size)
- **Version < 2.1**: Raw indexed data (width * height bytes)
- **Integration Point**: `src/parsers/spr_parser.py::_read_indexed_frame()`

#### 2.2 BGRA32 Image Loading
```csharp
protected GrfImage _loadBgra32Image(Rle rleImage)
```
- **Key**: Flips Y-axis (height - y - 1)
- **Color Order**: BGRA → RGBA conversion
- **Integration Point**: `src/parsers/spr_parser.py::_read_rgba_frame()`

#### 2.3 ACT Layer Compositing
- ActEditor uses `ActDraw.cs`, `LayerDraw.cs` for rendering
- **Integration Point**: `src/gui/grf_browser.py::_preview_act()`

---

## 3. Integration Strategy

### Option A: Fallback Parsers (Recommended)
**Pros**:
- Preserves existing code
- Only activates when current parser fails
- Gradual migration path

**Implementation**:
1. Create `src/extractors/grf_decompression_fallback.py`
2. Create `src/parsers/spr_parser_fallback.py`
3. Create `src/parsers/act_parser_fallback.py`
4. Integrate fallback calls in `grf_vfs.py` and `grf_browser.py`

### Option B: Replace Current Parsers
**Pros**:
- Single codebase to maintain
- Potentially better compatibility

**Cons**:
- Risk of breaking existing functionality
- Requires extensive testing

**Recommendation**: **Option A (Fallback Parsers)**

---

## 4. Dependencies Analysis

### GRFEditor Dependencies
- **Native DLLs**: `cps.dll`, `comp_x64.dll` (Gravity's zlib)
- **C# Libraries**: `zlib.net.dll`, `Encryption.dll`
- **Python Equivalents**:
  - `zlib` (standard library) - for zlib decompression
  - `lzma` (standard library) - for LZMA
  - `pycryptodome` or `cryptography` - for DES (if needed)

### ActEditor Dependencies
- **Native DLLs**: `ActImaging.dll` (image processing)
- **C# Libraries**: `GRF.dll`, `GrfToWpfBridge.dll`
- **Python Equivalents**:
  - `Pillow` (PIL) - already used
  - No additional dependencies needed

### Build/Packaging Impact
- **Current**: Uses PyInstaller
- **New Dependencies**: None (all standard library or already included)
- **Action Required**: None (Pillow already in requirements.txt)

---

## 5. Implementation Plan

### Phase 1: GRF Decompression Fallback
1. Port LZSS decompression algorithm
2. Add LZMA decompression (if not already present)
3. Enhance zlib fallback strategies
4. Integrate into `grf_vfs.py::_decompress_file()`

### Phase 2: SPR Parser Fallback
1. Port RLE decompression for SPR 2.1
2. Fix BGRA32 color order and Y-flip
3. Add version-specific frame reading
4. Integrate into `spr_parser.py::load_from_bytes()`

### Phase 3: ACT Parser Fallback
1. Port ACT layer compositing logic
2. Improve frame/anchor parsing
3. Integrate into `act_parser.py::load_from_bytes()`

### Phase 4: Preview Rendering Enhancement
1. Port frame compositing from ActEditor
2. Improve layer rendering in `grf_browser.py`
3. Add better error handling

---

## 6. Code Locations for Integration

### GRF Decompression
- **Primary**: `src/extractors/grf_vfs.py::_decompress_file()` (line ~681)
- **Fallback Entry**: Add `_decompress_file_grfeditor_fallback()` method
- **Call Site**: After current decompression fails

### SPR Parsing
- **Primary**: `src/parsers/spr_parser.py::load_from_bytes()` (line ~402)
- **Fallback Entry**: Add `_parse_spr_grfeditor_fallback()` method
- **Call Site**: When `load_from_bytes()` returns `None`

### ACT Parsing
- **Primary**: `src/parsers/act_parser.py::load_from_bytes()` (line ~462)
- **Fallback Entry**: Add `_parse_act_grfeditor_fallback()` method
- **Call Site**: When `load_from_bytes()` returns `None`

### Preview Rendering
- **Primary**: `src/gui/grf_browser.py::_preview_spr()`, `_preview_act()`
- **Enhancement**: Improve frame compositing logic
- **Call Site**: Within existing preview methods

---

## 7. Testing Strategy

### Unit Tests
- Test LZSS decompression with known data
- Test SPR RLE with version 2.1 files
- Test ACT parsing with various versions
- Test fallback activation when primary parser fails

### Integration Tests
- Load private server GRFs that fail with current parser
- Verify fallback activates correctly
- Ensure no performance regression

### Compatibility Tests
- Ensure existing GRFs still work
- Verify no breaking changes to API

---

## 8. Risk Assessment

### Low Risk
- Adding fallback parsers (doesn't change existing code)
- Porting LZSS algorithm (well-documented)
- Enhancing error messages

### Medium Risk
- Modifying existing decompression logic
- Changing SPR/ACT parser behavior
- Performance impact of fallback attempts

### Mitigation
- Keep fallback as opt-in initially
- Add feature flag to enable/disable fallbacks
- Extensive testing with various GRF files

---

## 9. Next Steps

1. **Confirm Integration Approach**: Fallback vs Replace
2. **Port Core Algorithms**: Start with LZSS and RLE
3. **Create Fallback Modules**: Separate files for clarity
4. **Integrate Gradually**: One module at a time
5. **Test Extensively**: Private server GRFs, edge cases
6. **Document Changes**: Update user guide

---

## 10. Questions for User

1. **Preference**: Fallback parsers or replace current implementation?
2. **Priority**: Which should be done first (GRF decompression, SPR, or ACT)?
3. **Testing**: Do you have specific private server GRFs that fail currently?
4. **Performance**: Acceptable to try fallback on every failure, or only for known problematic files?
