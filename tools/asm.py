#!/usr/bin/env python3
"""Hand-assembler for the small Thumb-2 stubs used by the Darkness Survival patch.

Only the handful of encodings actually needed are implemented; every emitted
branch is verified by disassembling the result with capstone.
"""
from capstone import *

COND = {'eq': 0x0, 'ne': 0x1, 'cs': 0x2, 'cc': 0x3, 'mi': 0x4, 'pl': 0x5,
        'vs': 0x6, 'vc': 0x7, 'hi': 0x8, 'ls': 0x9, 'ge': 0xA, 'lt': 0xB,
        'gt': 0xC, 'le': 0xD, 'al': 0xE}


def enc_bl(addr, target):
    imm = target - (addr + 4)
    assert -(1 << 24) <= imm < (1 << 24), 'BL out of range'
    S = (imm >> 24) & 1
    I1 = (imm >> 23) & 1
    I2 = (imm >> 22) & 1
    imm10 = (imm >> 12) & 0x3FF
    imm11 = (imm >> 1) & 0x7FF
    J1 = (~(I1 ^ S)) & 1
    J2 = (~(I2 ^ S)) & 1
    hi = 0xF000 | (S << 10) | imm10
    lo = 0xD000 | (J1 << 13) | (J2 << 11) | imm11
    return bytes([hi & 0xFF, hi >> 8, lo & 0xFF, lo >> 8])


def enc_b(addr, target):
    """16-bit unconditional B (T1)."""
    imm = target - (addr + 4)
    assert imm % 2 == 0 and -2048 <= imm <= 2046, f'B out of range: {imm}'
    h = 0xE000 | ((imm >> 1) & 0x7FF)
    return bytes([h & 0xFF, h >> 8])


def enc_bw(addr, target):
    """32-bit unconditional B (T4)."""
    imm = target - (addr + 4)
    assert -(1 << 24) <= imm < (1 << 24), 'B.W out of range'
    S = (imm >> 24) & 1
    I1 = (imm >> 23) & 1
    I2 = (imm >> 22) & 1
    imm10 = (imm >> 12) & 0x3FF
    imm11 = (imm >> 1) & 0x7FF
    J1 = (~(I1 ^ S)) & 1
    J2 = (~(I2 ^ S)) & 1
    hi = 0xF000 | (S << 10) | imm10
    lo = 0x9000 | (J1 << 13) | (J2 << 11) | imm11
    return bytes([hi & 0xFF, hi >> 8, lo & 0xFF, lo >> 8])


def enc_bcond(addr, target, cond):
    imm = target - (addr + 4)
    assert imm % 2 == 0 and -256 <= imm <= 254, f'B<cond> out of range: {imm}'
    h = 0xD000 | (COND[cond] << 8) | ((imm >> 1) & 0xFF)
    return bytes([h & 0xFF, h >> 8])


def enc_ldr_literal(addr, target, rt):
    pc = (addr + 4) & ~3
    imm = target - pc
    assert imm >= 0 and imm % 4 == 0 and imm <= 1020, f'literal out of range: {imm}'
    h = 0x4800 | (rt << 8) | (imm >> 2)
    return bytes([h & 0xFF, h >> 8])


class Asm:
    """Tiny two-pass assembler: items are ('label', name) or ('ins', kind, ...)."""

    def __init__(self, base):
        self.base = base
        self.items = []

    def label(self, name):
        self.items.append(('label', name)); return self

    def raw(self, hexstr):
        self.items.append(('raw', bytes.fromhex(hexstr))); return self

    def pcrel(self, kind, *args, label=None, cond=None):
        self.items.append(('branch', kind, args, label, cond)); return self

    def b(self, label):
        return self.pcrel('b', label=label)

    def bcond(self, cond, label):
        return self.pcrel('bcond', label=label, cond=cond)

    def bl(self, target):
        return self.pcrel('bl', target)

    def bw(self, label):
        return self.pcrel('bw', label=label)

    def ldr_literal(self, rt, label):
        return self.pcrel('ldrlit', rt, label=label)

    def resolve(self):
        # pass 1: compute addresses
        addr = self.base
        labels = {}
        addrs = []
        for it in self.items:
            addrs.append(addr)
            if it[0] == 'label':
                labels[it[1]] = addr
            elif it[0] == 'raw':
                addr += len(it[1])
            elif it[0] == 'branch':
                addr += 4 if it[1] in ('bl', 'bw') else 2
        # pass 2: emit
        out = bytearray()
        for it, a in zip(self.items, addrs):
            if it[0] == 'label':
                continue
            if it[0] == 'raw':
                out += it[1]
            elif it[0] == 'branch':
                kind, args, lab, cond = it[1], it[2], it[3], it[4]
                tgt = labels[lab] if kind in ('b', 'bcond', 'ldrlit', 'bw') else args[0]
                if kind == 'b':
                    out += enc_b(a, tgt)
                elif kind == 'bcond':
                    out += enc_bcond(a, tgt, cond)
                elif kind == 'bl':
                    out += enc_bl(a, tgt)
                elif kind == 'bw':
                    out += enc_bw(a, tgt)
                elif kind == 'ldrlit':
                    out += enc_ldr_literal(a, tgt, args[0])
        self.labels = labels
        return bytes(out)


def show(code, base, title=''):
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    print(f'--- {title} @0x{base:08x} ({len(code)} bytes) ---')
    for i in md.disasm(code, base):
        print(f'  0x{i.address:08x}: {i.bytes.hex():<10} {i.mnemonic:<7} {i.op_str}')
