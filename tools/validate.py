#!/usr/bin/env python3
"""Validate translated textdata strings against the game font's glyph set.

Checks, per entry:
  * every character exists in SeoulNamsanEB.ttf's cmap (else it renders blank)
  * colour markup <C........> preserved exactly, same order/count
  * printf specifiers (%s %d %ld %f %u) preserved with the same multiset
  * no leftover Hangul
  * entry count / ids match the source batch

Usage: python3 zh/validate.py            # validate everything in zh/out
"""
import json, re, sys, glob, os

ROOT = '/home/pmtest/dsh-verify'
ALLOWED = set(json.load(open(f'{ROOT}/zh/font_chars.json')))
TAG = re.compile(r'<C[0-9A-Fa-f]{8}>')
FMT = re.compile(r'%[-+ #0-9.]*(?:l|h|z|j|t|L)?[diouxXeEfgGcs%]')
HANGUL = re.compile(r'[\uac00-\ud7a3]')


def validate(entries, src):
    """entries: list of {"id","zh"}; src: {id: {"ko","en"}}"""
    problems = []
    for e in entries:
        i, zh = e.get('id'), e.get('zh', '')
        s = src.get(i)
        if s is None:
            problems.append((i, 'unknown id', ''))
            continue
        # glyph coverage
        bad = sorted({c for c in zh if ord(c) not in ALLOWED})
        if bad:
            problems.append((i, 'missing glyph', ''.join(bad) + ' :: ' + zh))
        # markup
        if TAG.findall(s['ko']) != TAG.findall(zh) and TAG.findall(s.get('en', '')) != TAG.findall(zh):
            problems.append((i, 'markup mismatch', f'{TAG.findall(s["ko"])} -> {TAG.findall(zh)}'))
        # printf specifiers
        if sorted(FMT.findall(s['ko'])) != sorted(FMT.findall(zh)) and \
           sorted(FMT.findall(s.get('en', ''))) != sorted(FMT.findall(zh)):
            problems.append((i, 'format mismatch', f'{FMT.findall(s["ko"])} -> {FMT.findall(zh)}'))
        # hangul left over
        if HANGUL.search(zh):
            problems.append((i, 'hangul remains', zh))
        if not zh.strip():
            problems.append((i, 'empty translation', ''))
    return problems


def main():
    src = {e['id']: e for e in json.load(open(f'{ROOT}/zh/strings.json'))}
    files = sorted(glob.glob(f'{ROOT}/zh/out/batch_*.json'))
    if not files:
        print('no output batches yet'); return 1
    total = bad_total = 0
    allp = []
    for f in files:
        try:
            entries = json.load(open(f))
        except Exception as ex:
            print(f'{os.path.basename(f)}: JSON ERROR {ex}'); bad_total += 1; continue
        total += len(entries)
        p = validate(entries, src)
        allp += [(os.path.basename(f),) + x for x in p]
        if p:
            bad_total += len(p)
            print(f'{os.path.basename(f)}: {len(p)} problem(s)')
            for i, kind, detail in p[:6]:
                print(f'    id={i:<5} {kind:<18} {detail[:90]}')
    print(f'\nchecked {len(files)} batch(es), {total} entries, {bad_total} problem(s)')
    json.dump(allp, open(f'{ROOT}/zh/problems.json', 'w'), ensure_ascii=False, indent=1)
    return 1 if bad_total else 0


if __name__ == '__main__':
    sys.exit(main())
