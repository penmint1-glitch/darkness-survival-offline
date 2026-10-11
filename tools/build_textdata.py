#!/usr/bin/env python3
"""Read / rebuild the game's textdata_*.dat files.

Format (little endian, verified against the shipped files):

    u32  table_bytes        == 4 * count
    u32  offsets[count]     byte offset of each string, relative to blob start
    u32  blob_size          total byte length of the string blob
    u8   blob[]             UTF-8, NUL-terminated strings, back to back

`TextDataManager::getText(id)` returns `blob + offsets[id]` and
`TextDataManager::loadTextData()` sets count = table_bytes / 4, so the table
layout has to match exactly.
"""
import struct, sys, json


def read(path):
    """Return (offsets, strings, blob_extra)."""
    d = open(path, 'rb').read()
    table_bytes = struct.unpack_from('<I', d, 0)[0]
    count = table_bytes // 4
    offs = list(struct.unpack_from('<%dI' % count, d, 4))
    blob_off = 4 + table_bytes + 4
    blob_size = struct.unpack_from('<I', d, 4 + table_bytes)[0]
    assert blob_off + blob_size == len(d), (blob_off + blob_size, len(d))
    out = []
    for o in offs:
        p = blob_off + o
        e = d.index(b'\0', p)
        out.append(d[p:e].decode('utf-8'))
    return offs, out


def write(path, strings):
    blob = bytearray()
    offs = []
    for s in strings:
        offs.append(len(blob))
        blob += s.encode('utf-8') + b'\0'
    count = len(strings)
    head = struct.pack('<I', count * 4)
    head += struct.pack('<%dI' % count, *offs)
    head += struct.pack('<I', len(blob))
    data = head + bytes(blob)
    open(path, 'wb').write(data)
    return data


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'roundtrip':
        _, src = read(sys.argv[2])
        orig = open(sys.argv[2], 'rb').read()
        new = write('/tmp/rt.dat', src)
        print(f'{sys.argv[2]}: {len(src)} strings, original {len(orig)}B rebuilt {len(new)}B '
              f'-> {"BYTE-IDENTICAL" if orig == new else "DIFFERS"}')
        if orig != new:
            for i in range(min(len(orig), len(new))):
                if orig[i] != new[i]:
                    print(f'  first diff at {i:#x}: {orig[i]:#x} vs {new[i]:#x}')
                    break
        sys.exit(0 if orig == new else 1)
    if len(sys.argv) == 4 and sys.argv[1] == 'apply':
        base_path, trans_path, out_path = sys.argv[2], sys.argv[3], sys.argv[4]
        _, strings = read(base_path)
        trans = json.load(open(trans_path))
        for k, v in trans.items():
            strings[int(k)] = v
        write(out_path, strings)
        print(f'applied {len(trans)} translations -> {out_path}')
        sys.exit(0)
    print(__doc__)
