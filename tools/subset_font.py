#!/usr/bin/env python3
"""Subset the bundled CJK font down to the characters the game actually renders.

The Simplified builds install one font into BOTH `assets/SeoulNamsanEB.ttf` and
`assets/arial.ttf`. Shipping the full Noto Sans SC face (30,890 glyphs,
8,331,336 bytes) in two slots cost ~13 MB of APK; only ~1,700 characters are ever
used, so we subset.

The character set is the union of:
  * every character in the translated text table,
  * every character in the shipped Cocos Studio `.csb` layouts,
  * printable ASCII,
  * the punctuation actually used by those strings.

Usage:
    python3 subset_font.py <source.otf> <textdata.dat> <extracted-assets-dir> <out-dir>

Writes <out-dir>/SeoulNamsanEB.ttf and <out-dir>/arial.ttf and prints a coverage
report. A missing glyph does NOT crash this game (it renders blank) -- an earlier
investigation wrongly blamed the font for a crash that was really caused by
editing the `.csb` layouts -- but blank CJK text is still a bug, so check the
report says 0 missing.
"""
import os
import sys
import zipfile

from fontTools import subset
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_textdata import read          # noqa: E402
from csb import extract                  # noqa: E402

EXTRA = set('　、。〈〉《》「」『』【】〔〕・ー―‐–—…※★☆♪→←↑↓')


def collect(textdata, assets_dir):
    chars = set()
    _, strings = read(textdata)
    for s in strings:
        chars |= set(s)
    for root, _dirs, files in os.walk(assets_dir):
        for name in files:
            if not name.endswith('.csb'):
                continue
            try:
                _, rows = extract(os.path.join(root, name))
                for row in rows:
                    chars |= set(row['text'])
            except Exception:
                pass
    chars |= {chr(c) for c in range(0x20, 0x7F)}
    chars |= EXTRA
    return {c for c in chars if c.strip() or c == ' '}


def main():
    src, textdata, assets_dir, out_dir = sys.argv[1:5]
    chars = collect(textdata, assets_dir)
    opts = subset.Options()
    opts.layout_features = []
    opts.no_hinting = True
    opts.desubroutinize = True
    opts.drop_tables += ['DSIG']
    font = subset.load_font(src, opts)
    sub = subset.Subsetter(options=opts)
    sub.populate(text=''.join(sorted(chars)))
    sub.subset(font)
    os.makedirs(out_dir, exist_ok=True)
    for slot in ('SeoulNamsanEB.ttf', 'arial.ttf'):
        subset.save_font(font, os.path.join(out_dir, slot), opts)

    face = TTFont(os.path.join(out_dir, 'arial.ttf'), fontNumber=0)
    cmap = set()
    for table in face['cmap'].tables:
        cmap |= set(table.cmap.keys())
    missing = sorted(c for c in chars if ord(c) not in cmap)
    size = os.path.getsize(os.path.join(out_dir, 'arial.ttf'))
    print(f'{len(chars)} characters -> {len(cmap)} glyphs, {size:,} bytes per slot')
    print(f'missing: {len(missing)} {missing[:20]}')
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
