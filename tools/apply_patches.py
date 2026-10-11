#!/usr/bin/env python3
"""Apply PATCHES from patchdefs.py to libcocos2dcpp.so."""
import sys, os, struct
import patchdefs as P
WHITELIST = '--whitelist' in sys.argv

SRC = 'apk/lib/armeabi/libcocos2dcpp.so'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'work/libcocos2dcpp.so'

# Sanity anchors: the first bytes we expect to find at each site in the input
# APK (which already carries the upstream community patch).
ANCHORS = {
    P.GETGAMENETSTATE:  bytes.fromhex('00687047'),
    P.SENDPACKET_JUMP:  bytes.fromhex('0368'),
    P.SENDDATAWZPP:     bytes.fromhex('f7b5'),
    P.SENDDATA:         bytes.fromhex('10b5'),
    P.SIGNIN:           bytes.fromhex('10b5'),
    P.GETNETWORKSTATUS: bytes.fromhex('052040427047'),   # upstream 6-byte stub
    P.GET_ACHIEVEMENT_ID:     bytes.fromhex('08b5034b0221c018'),
    P.GET_ACHIEVEMENT_REWARD: bytes.fromhex('08b5034b0621c018'),
    P.GET_NEWBOX_GETTYPE:     bytes.fromhex('08b5034b0e21c018'),
    P.GET_NEW_MEDAL_NUM:      bytes.fromhex('08b5034b0221c018'),
    P.GET_IAP_MEDAL_NUM:      bytes.fromhex('08b5034b0621c018'),
    P.GET_USER_ID:            bytes.fromhex('08b5034b0221c018'),
    P.GET_BOX_MEDAL_ADD:      bytes.fromhex('08b5034b4021c018'),
    P.GET_ADBOX_MEDAL_ADD:    bytes.fromhex('08b5034b4021c018'),
    P.GET_BOX_ANKH_ADD:       bytes.fromhex('08b5034b4421c018'),
    P.GET_MEDALBOX_ANKH_ADD:  bytes.fromhex('08b5034b3c21c018'),
    P.RUNE_COIN_STORE:   bytes.fromhex('f850'),
    P.RECIPE_COIN_STORE: bytes.fromhex('f850'),
    P.RESUR_ANKH_STORE:  bytes.fromhex('f050'),
    P.RESUR_COIN_STORE:  bytes.fromhex('f050'),
}

data = bytearray(open(SRC, 'rb').read())
print(f'source: {SRC} ({len(data):,} bytes)')
for off, orig, new, desc in (P.build_patches(WHITELIST)[0] if WHITELIST else P.PATCHES):
    anchor = ANCHORS.get(off)
    if anchor:
        got = bytes(data[off:off + len(anchor)])
        if got != anchor:
            raise SystemExit(f'ANCHOR MISMATCH at 0x{off:x} ({desc})\n'
                             f'  expected {anchor.hex()}\n  found    {got.hex()}')
    if orig is not None and bytes(data[off:off + len(orig)]) != orig:
        raise SystemExit(f'ORIGINAL MISMATCH at 0x{off:x} ({desc})')
    data[off:off + len(new)] = new
    print(f'  patched 0x{off:06x} ({len(new):>3}B)  {desc}')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'wb').write(bytes(data))
print(f'wrote {OUT} ({len(data):,} bytes)')
