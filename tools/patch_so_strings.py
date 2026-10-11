#!/usr/bin/env python3
"""Translate the room/location names hard-coded in libcocos2dcpp.so's rodata.

These 36 strings are referenced by absolute pointers (a table at 0xb41000+), so
they must stay at their exact addresses: each replacement is written in place and
NUL-padded to the original byte length.  Nothing else in the file moves.

Usage: python3 zh/patch_so_strings.py <in.so> <out.so> [trad|simp]
Default variant is 'trad'.
"""
import sys, os

# (offset, original byte length excluding NUL, korean, traditional, simplified)
ROOMS = [
    (0x79552a, 10, '보스방1',       '首領房1',   '首领房1'),
    (0x795535, 10, '보스방2',       '首領房2',   '首领房2'),
    (0x795540, 10, '보스방3',       '首領房3',   '首领房3'),
    (0x79554b, 10, '보스방4',       '首領房4',   '首领房4'),
    (0x795556, 10, '보스방5',       '首領房5',   '首领房5'),
    (0x795561,  6, '상점',          '商店',      '商店'),
    (0x795568, 19, '올라가는 계단',  '上樓階梯',  '上楼阶梯'),
    (0x79557c, 19, '내려가는 계단',  '下樓階梯',  '下楼阶梯'),
    (0x795590,  6, '정원',          '庭園',      '庭园'),
    (0x795597,  9, '트랩방',        '機關房',    '机关房'),
    (0x7955a1,  3, '샘',            '泉',        '泉'),
    (0x7955a5, 13, '오염된 샘',      '汚染之泉',  '污染之泉'),
    (0x7955b3,  6, '우물',          '水井',      '水井'),
    (0x7955ba,  6, '캠프',          '營地',      '营地'),
    (0x7955c1, 19, '마법지식의 방',  '魔法知識室', '魔法知识室'),
    (0x7955d5, 19, '무기지식의 방',  '武器知識室', '武器知识室'),
    (0x7955e9,  9, '무덤방',        '墳墓房',    '坟墓房'),
    (0x7955f3, 13, '피라냐 방',      '食人魚房',  '食人鱼房'),
    (0x795601, 16, '낭떠러지 방',    '懸崖房間',  '悬崖房间'),
    (0x795612,  6, '신전',          '神殿',      '神殿'),
    (0x795619,  9, '기념관',        '紀念館',    '纪念馆'),
    (0x795623, 12, '연금술방',       '鍊金術房',  '炼金术房'),
    (0x795630, 12, '보물창고',       '寶物倉庫',  '宝物仓库'),
    (0x79563d,  9, '무기고',        '武器庫',    '武器库'),
    (0x795647,  6, '서고',          '書庫',      '书库'),
    (0x79564e,  6, '금고',          '金庫',      '金库'),
    (0x795655,  6, '제단',          '祭壇',      '祭坛'),
    (0x79565c,  9, '석상실',        '石像室',    '石像室'),
    (0x795666,  6, '묘소',          '墓地',      '墓地'),
    (0x79566d, 19, '보물헌터의 방',  '尋寶者之房', '寻宝者之房'),
    (0x795681, 13, '무너진 방',      '崩壞房間',  '崩坏房间'),
    (0x79568f, 19, '바리케이드 방',  '路障房間',  '路障房间'),
    (0x7956a3,  6, '농장',          '農場',      '农场'),
    (0x7956aa, 13, '트랩만 방',      '純機關房',  '纯机关房'),
    (0x7956b8, 10, '꺼진 방',       '熄滅房',    '熄灭房'),
    (0x7956c3, 15, '세미보스방',      '準首領房',  '准首领房'),
]
IDX = {'trad': 3, 'simp': 4}


def patch(data: bytes, variant: str = 'trad') -> bytes:
    col = IDX[variant]
    d = bytearray(data)
    for row in ROOMS:
        off, L, ko, zh = row[0], row[1], row[2], row[col]
        cur = bytes(d[off:off + L]).decode('utf-8')
        if cur != ko:
            raise SystemExit(f'anchor mismatch at {off:#x}: {cur!r} != {ko!r}')
        if d[off + L] != 0:
            raise SystemExit(f'missing NUL terminator at {off + L:#x}')
        zb = zh.encode('utf-8')
        if len(zb) > L:
            raise SystemExit(f'{zh!r} needs {len(zb)}B but only {L}B available at {off:#x}')
        d[off:off + len(zb)] = zb
        d[off + len(zb):off + L + 1] = b'\0' * (L + 1 - len(zb))
    return bytes(d)


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    variant = sys.argv[3] if len(sys.argv) > 3 else 'trad'
    data = open(src, 'rb').read()
    out = patch(data, variant)
    diff = sum(1 for a, b in zip(data, out) if a != b)
    open(dst, 'wb').write(out)
    print(f'{src} -> {dst} [{variant}]: {len(ROOMS)} room names, {diff} bytes changed')
    col = IDX[variant]
    for row in ROOMS:
        off, L, ko, zh = row[0], row[1], row[2], row[col]
        got = out[off:off + L + 1].split(b'\0')[0].decode('utf-8')
        assert got == zh, (hex(off), got, zh)
    print('readback verified for all', len(ROOMS), 'strings')
