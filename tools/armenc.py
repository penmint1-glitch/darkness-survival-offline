#!/usr/bin/env python3
"""Minimal Thumb-1/Thumb-2 encoders with built-in disassembly verification.

Every instruction is emitted through `Code.op()`, which records the exact
disassembly text the encoder believes it produced.  `Code.verify()` then runs
capstone over the assembled bytes and asserts an exact match, so a mis-encoded
register or immediate fails loudly at build time instead of silently patching
the wrong thing.
"""
from capstone import *

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def _h(hw):
    return bytes([hw & 0xFF, (hw >> 8) & 0xFF])


# ---- 16-bit Thumb encoders --------------------------------------------------
def movs(rd, imm):        return _h(0x2000 | (rd << 8) | (imm & 0xFF))
def cmp_imm(rn, imm):     return _h(0x2800 | (rn << 8) | (imm & 0xFF))
def adds_imm(rd, imm):    return _h(0x3000 | (rd << 8) | (imm & 0xFF))
def subs_imm(rd, imm):    return _h(0x3800 | (rd << 8) | (imm & 0xFF))
def adds_reg(rd, rn, rm): return _h(0x1800 | (rm << 6) | (rn << 3) | rd)
def ands(rd, rm):         return _h(0x4000 | (rm << 3) | rd)
def lsls(rd, rm, sh):     return _h(0x0000 | (sh << 6) | (rm << 3) | rd)
def str_reg(rt, rn, rm):  return _h(0x5000 | (rm << 6) | (rn << 3) | rt)
def strb_reg(rt, rn, rm): return _h(0x5400 | (rm << 6) | (rn << 3) | rt)
def str_imm(rt, rn, off): return _h(0x6000 | (((off) >> 2) << 6) | (rn << 3) | rt)
def ldr_imm(rt, rn, off): return _h(0x6800 | (((off) >> 2) << 6) | (rn << 3) | rt)
def strb_imm(rt, rn, off):return _h(0x7000 | (off << 6) | (rn << 3) | rt)
def ldrb_imm(rt, rn, off):return _h(0x7800 | (off << 6) | (rn << 3) | rt)
def push(reglist, lr=False): return _h(0xB400 | (0x100 if lr else 0) | reglist)
def pop(reglist, pc=False):  return _h(0xBC00 | (0x100 if pc else 0) | reglist)
def rsbs(rd, rm, imm=0):  return _h(0x4240 | (rm << 3) | rd)
BX_LR = _h(0x4770)
NOP   = _h(0xBF00)

R = {'r0': 0, 'r1': 1, 'r2': 2, 'r3': 3, 'r4': 4, 'r5': 5, 'r6': 6, 'r7': 7}


def movw(rd, imm16):
    """movw rd, #imm16  (32-bit MOV immediate, T3)."""
    imm4 = (imm16 >> 12) & 0xF
    i = (imm16 >> 11) & 1
    imm3 = (imm16 >> 8) & 7
    imm8 = imm16 & 0xFF
    return _h(0xF240 | (i << 10) | imm4) + _h((imm3 << 12) | (rd << 8) | imm8)


def rev(rd, rm):
    """rev rd, rm  (byte-reverse, T1: 1011 1010 00 Rm Rd)."""
    return _h(0xBA00 | (rm << 3) | rd)


def addw(rd, rn, imm12):
    """addw rd, rn, #imm12  (32-bit ADD immediate, T4)."""
    i = (imm12 >> 11) & 1
    imm3 = (imm12 >> 8) & 7
    imm8 = imm12 & 0xFF
    hw1 = 0xF200 | (i << 10) | rn
    hw2 = (imm3 << 12) | (rd << 8) | imm8
    return _h(hw1) + _h(hw2)


def ldr_imm_wide(rt, rn, imm12):
    """ldr.w rt, [rn, #imm12]  (32-bit LDR immediate, T3)."""
    hw1 = 0xF8D0 | rn
    hw2 = (rt << 12) | imm12
    return _h(hw1) + _h(hw2)


def str_imm_wide(rt, rn, imm12):
    hw1 = 0xF8C0 | rn
    hw2 = (rt << 12) | imm12
    return _h(hw1) + _h(hw2)


class Code:
    """Accumulates instructions together with their expected disassembly."""

    def __init__(self, base):
        self.base = base
        self.buf = bytearray()
        self.expect = []
        self.labels = {}

    def op(self, raw, text):
        self.expect.append((len(self.buf), text))
        self.buf += raw
        return self

    def label(self, name):
        self.labels[name] = self.base + len(self.buf)
        return self

    def addr(self):
        return self.base + len(self.buf)

    # branches are resolved in a second pass
    def branch(self, kind, target_label, cond=None):
        self.expect.append((len(self.buf), f'__{kind}:{target_label}:{cond}'))
        self.buf += b'\x00\x00' if kind in ('b', 'bcond') else b'\x00\x00\x00\x00'
        return self

    def resolve(self):
        from asm import enc_b, enc_bw, enc_bcond, enc_bl
        out = bytearray(self.buf)
        for off, text in self.expect:
            if not text.startswith('__'):
                continue
            kind, label, cond = text[2:].split(':')
            a = self.base + off
            tgt = self.labels[label]
            if kind == 'b':
                out[off:off + 2] = enc_b(a, tgt)
            elif kind == 'bcond':
                out[off:off + 2] = enc_bcond(a, tgt, cond)
            elif kind == 'bw':
                out[off:off + 4] = enc_bw(a, tgt)
            elif kind == 'bl':
                out[off:off + 4] = enc_bl(a, tgt)
        return bytes(out)

    def verify(self, name='code'):
        code = self.resolve()
        got = list(md.disasm(code, self.base))
        exp = []
        for o, t in self.expect:
            a = self.base + o
            if t.startswith('__'):
                kind, label, cond = t[2:].split(':')
                tgt = self.labels[label]
                if kind == 'b' or kind == 'bw':
                    t = f'b #{tgt:#x}'
                elif kind == 'bcond':
                    t = f'b{cond} #{tgt:#x}'
                elif kind == 'bl':
                    t = f'bl #{tgt:#x}'
            exp.append((a, t))
        ok = True
        if len(exp) != len(got):
            print(f'  !! {name}: instruction count mismatch {len(exp)} vs {len(got)}')
            ok = False
        for (a, t), ins in zip(exp, got):
            actual = f'{ins.mnemonic} {ins.op_str}'.strip()
            if actual != t.strip():
                print(f'  !! {name} @0x{a:06x}: expected "{t}" got "{actual}"')
                ok = False
        return ok, code


def imm(v):
    """Format an immediate the way capstone does (decimal <=9, else hex)."""
    return f'#{v}' if v <= 9 else f'#0x{v:x}'
