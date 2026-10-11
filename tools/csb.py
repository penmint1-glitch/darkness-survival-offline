#!/usr/bin/env python3
"""Read and patch strings inside Cocos Studio `.csb` files (raw FlatBuffers).

A FlatBuffers string is stored as:

    u32 length | <length bytes of UTF-8> | 0x00

and is referenced by a uoffset stored elsewhere: `target = ref_pos + u32(ref_pos)`.

`extract()` finds every *referenced* string (so binary noise is ignored).
`patch()` rewrites chosen strings by appending the replacement at the end of the
buffer and re-pointing every reference at it -- old bytes are simply orphaned,
which is harmless because FlatBuffers are read by following relative offsets.
"""
import struct, sys, json, glob, os

HANGUL = __import__('re').compile(r'[\uac00-\ud7a3]')


def _refmap(d):
    m = {}
    for p in range(0, len(d) - 4, 4):
        v = struct.unpack_from('<I', d, p)[0]
        t = p + v
        if 0 < t < len(d):
            m.setdefault(t, []).append(p)
    return m


def extract(path):
    """Return list of dicts: offset, text, refs."""
    d = open(path, 'rb').read()
    refs = _refmap(d)
    out = []
    for s in sorted(refs):
        if s + 5 > len(d):
            continue
        L = struct.unpack_from('<I', d, s)[0]
        if L == 0 or L > len(d) - s - 5 or L > 4096:
            continue
        end = s + 4 + L
        if d[end] != 0:
            continue
        raw = d[s + 4:end]
        if b'\0' in raw:
            continue
        try:
            t = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        out.append({'offset': s, 'text': t, 'refs': refs[s]})
    return d, out


def patch(path, repl, out_path):
    """repl: {offset: new_text}. Appends replacements and re-points references."""
    d = bytearray(open(path, 'rb').read())
    _, strings = extract(path)
    by_off = {s['offset']: s for s in strings}
    appended = []
    for off, txt in repl.items():
        s = by_off.get(off)
        if s is None:
            raise SystemExit(f'no string at {off:#x} in {path}')
        if txt == s['text']:
            continue
        blob = txt.encode('utf-8')
        while len(d) % 4:
            d.append(0)
        new_off = len(d)
        d += struct.pack('<I', len(blob)) + blob + b'\0'
        for p in s['refs']:
            struct.pack_into('<I', d, p, new_off - p)
        appended.append((off, new_off, s['text'], txt))
    open(out_path, 'wb').write(bytes(d))
    return appended


if __name__ == '__main__':
    if sys.argv[1] == 'list':
        tot = 0
        for p in sorted(glob.glob(f'{sys.argv[2]}/**/*.csb', recursive=True)):
            d, ss = extract(p)
            ko = [s for s in ss if HANGUL.search(s['text'])]
            if ko:
                tot += len(ko)
                print(f'{os.path.basename(p)}: {len(ss)} strings, {len(ko)} korean')
        print('total korean strings:', tot)
