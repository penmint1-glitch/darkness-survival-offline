#!/usr/bin/env python3
"""Apply Chinese translations to every .csb that contains Korean UI text.

Uses zh/csb.py: replacements are appended to the FlatBuffers buffer and every
reference is re-pointed, so string lengths may change freely.
"""
import sys, os, json, glob, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csb import extract, patch, HANGUL

ROOT = '/home/pmtest/dsh-verify'
SRC = f'{ROOT}/apk/assets'


def main(trans_file=None, dst=None):
    trans = json.load(open(trans_file or f'{ROOT}/zh/csb_zh.json'))
    DST = dst or f'{ROOT}/work/assets_zh'
    os.makedirs(DST, exist_ok=True)
    nfiles = nstr = 0
    missing = set()
    for p in sorted(glob.glob(f'{SRC}/**/*.csb', recursive=True)):
        rel = os.path.relpath(p, SRC)
        out = os.path.join(DST, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        _, strings = extract(p)
        repl = {}
        for s in strings:
            if not HANGUL.search(s['text']):
                continue
            zh = trans.get(s['text'])
            if zh is None:
                missing.add(s['text'])
                continue
            if zh != s['text']:
                repl[s['offset']] = zh
        if repl:
            patch(p, repl, out)
            nfiles += 1
            nstr += len(repl)
        else:
            shutil.copyfile(p, out)
    print(f'patched {nstr} strings in {nfiles} .csb files -> {DST}')
    if missing:
        print(f'!! {len(missing)} korean strings had no translation:')
        for m in sorted(missing)[:20]:
            print('   ', repr(m))
    # verify: every patched file re-reads with the Chinese text
    bad = 0
    for p in sorted(glob.glob(f'{DST}/**/*.csb', recursive=True)):
        _, strings = extract(p)
        for s in strings:
            if HANGUL.search(s['text']):
                bad += 1
                if bad <= 5:
                    print('   still korean:', os.path.basename(p), repr(s['text'][:40]))
    print('strings still Korean after patch:', bad)
    return 0 if (not missing and bad == 0) else 1


if __name__ == '__main__':
    tf = sys.argv[1] if len(sys.argv) > 1 else None
    dd = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(main(tf, dd))
