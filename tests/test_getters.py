#!/usr/bin/env python3
"""Execute the patched GameNet getters under Unicorn with a mocked ProgressInfo.

Verifies the value-supplying half of the patch: the getters that feed the reply
handler must return sane, non-destructive values.
"""
import sys, struct
from unicorn import *
from unicorn.arm_const import *

SO = sys.argv[1] if len(sys.argv) > 1 else 'work/libcocos2dcpp.so'
DATA = open(SO, 'rb').read()

CODE_LO, CODE_HI = 0x3a0000, 0x3e0000      # covers ProgressInfo, GameNet, ZPPTCPNetwork
GN = 0x00100000                            # fake GameNet
PI = 0x00110000                            # fake ProgressInfo
STACK = 0x00200000
RET = 0x00300000
PROGRESSINFO_GET = 0x3a3124
COINS_OFF = 0x704
ANKH_OFF = 0x708
PROGKEY_OFF = 0x8

fail = 0


def check(cond, msg):
    global fail
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        fail += 1


def signed(v):
    return v - (1 << 32) if v >= (1 << 31) else v


def call(entry, sendbuf=None, coins=1000, ankh=7, progkey=0xDEADBEEF):
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    mu.mem_map(CODE_LO, CODE_HI - CODE_LO)
    mu.mem_write(CODE_LO, DATA[CODE_LO:CODE_HI])
    mu.mem_map(GN & ~0xFFFF, 0x20000)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(RET & ~0xFFF, 0x1000)
    mu.mem_write(PI, b'\x00' * 0x1000)
    mu.mem_write(PI + PROGKEY_OFF, struct.pack('<I', progkey))
    mu.mem_write(PI + COINS_OFF, struct.pack('<I', coins))
    mu.mem_write(PI + ANKH_OFF, struct.pack('<I', ankh))
    mu.mem_write(GN, b'\x00' * 0x10000)
    if sendbuf is not None:
        mu.mem_write(GN + 0x0c, sendbuf.ljust(32, b'\x00'))
    mu.reg_write(UC_ARM_REG_SP, STACK + 0x8000)
    mu.reg_write(UC_ARM_REG_R0, GN)
    mu.reg_write(UC_ARM_REG_LR, RET | 1)

    def hook_pi(uc, addr, size, user):
        uc.reg_write(UC_ARM_REG_R0, PI)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    mu.hook_add(UC_HOOK_CODE, hook_pi, begin=PROGRESSINFO_GET, end=PROGRESSINFO_GET)
    mu.hook_add(UC_HOOK_CODE, lambda uc, a, s, u: uc.emu_stop()
                if (a & ~1) == RET else None)
    mu.emu_start(entry | 1, RET, count=100000)
    return signed(mu.reg_read(UC_ARM_REG_R0))


print('--- GameNet::getNewMedalNum()  (reply 24/42 assigns PI[0x704]) ---')
v = call(0x3d6f58, coins=1000)
check(v == 1005, f'returns coins+5 == 1005 (got {v}) -> assignment is not a wipe')
v = call(0x3d6f58, coins=0)
check(v == 5, f'returns 5 when the balance is 0 (got {v})')

print('--- GameNet::getInAppBillingMedalNum()  (reply 16 assigns PI[0x704]) ---')
v = call(0x3d6c04, coins=4242)
check(v == 4242, f'returns the live balance 4242 (got {v}) -> no wipe, no free purchase')

print('--- GameNet::getUserId()  (reply 8/26 assigns PI+8) ---')
v = call(0x3d6430, progkey=0xCAFEF00D)
check(v == signed(0xCAFEF00D), f'returns the live save key (got {v:#x})')

print('--- GameNet::getAchievementReward() ---')
v = call(0x3d6e38)
check(v == 1000, f'returns 1000 Ancient Coins (got {v})')

print('--- GameNet::getBoxRewardMedalAdd() / getAdBoxRewardMedalAdd() ---')
check(call(0x3d6860) == 50, 'box reward = +50 Ancient Coins')
check(call(0x3d689c) == 50, 'ad box reward = +50 Ancient Coins')
print('--- GameNet::getBoxRewardAnkhAdd() / getMedalBoxRewardAnkhAdd() ---')
check(call(0x3d6874) == 1, 'box ankh = +1')
check(call(0x3d68b0) == 1, 'medal box ankh = +1 (offsets the fixed -600 coin cost)')

print('--- GameNet::getAchievementId()  (clamped echo of the claimed id) ---')
for claimed, expect in [(0, 0), (5, 5), (84, 84), (85, 0), (1000, 0)]:
    sb = bytearray(32)
    sb[7:11] = struct.pack('>I', claimed)          # prepareRequestAchievementReward writes BE
    v = call(0x3d6e24, sendbuf=bytes(sb))
    check(v == expect, f'claimed id {claimed} -> {v} (expect {expect})')

print('--- GameNet::getNewBoxGetType()  (echoes request arg2) ---')
for arg2 in (0, 1, 2, 3):
    sb = bytearray(32)
    sb[11:15] = struct.pack('>I', arg2)            # prepareNewBox writes arg2 at sendbuf[11]
    v = call(0x3d6eec, sendbuf=bytes(sb))
    check(v == arg2, f'arg2 {arg2} -> {v} (drives UIMainmenu when 1 or 3)')

print()
print('RESULT:', 'ALL PASS' if fail == 0 else f'{fail} FAILURE(S)')
sys.exit(1 if fail else 0)
