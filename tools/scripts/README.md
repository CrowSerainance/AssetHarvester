# BMS Scripts Directory

Place QuickBMS scripts (.bms files) here for various game formats.

## Usage

```python
from src.extractors import GenericExtractor

extractor = GenericExtractor()
extractor.set_script("tools/scripts/mygame.bms")
extractor.open("archive.pak")
extractor.extract_all("output/")
```

## Script Sources

- https://aluigi.altervista.org/papers.htm
- https://zenhax.com/
- Game-specific modding communities
