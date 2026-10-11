#!/usr/bin/env python3
"""End-to-end Unicorn check of the memory-box reward.

Runs BOTH sides of the protocol against the real patched code:

  1. GameNet::getNetworkStatus() (the responder) with request 21 pending ->
     it must synthesise reply 22 with result 0 and the box payload.
  2. The real reply-22 handler at 0x3c1b54, fed that very reply, must store the
     memory item into ProgressInfo's 6-slot box array at +0x23C (stride 12) and
     leave the box type in the first dword, the ground level in the second and
     -1 in the third.

Only ProgressInfo::getInstance / save and GameNet::disconnect are stubbed; the
box getters and ZPPTCPNetwork::getPacketInt run for real, so the big-endian
payload encoding is validated too.

Usage: PYTHONPATH=pylibs python3 test_box_reward.py work/libcocos2dcpp.so
"""
import sys, struct
from unicorn import *
from unicorn.arm_const import *

SO = sys.argv[1] if len(sys.argv) > 1 else 'work/libcocos2dcpp.so'
d = open(SO, 'rb').read()

RESPONDER = 0x3d5d04          # GameNet::getNetworkStatus (patched)
HANDLER = 0x3c1b54            # UILayer::networking() reply-22 case
BOX_STOP = 0x3c1bf6           # stop right after the box writes
PI_GET = 0x3a3124
PI_SAVE = 0x3a2254
DISCONNECT = 0x3d5e68

GN = 0x00100000
STACK = 0x00200000
RET = 0x00300000
PI = 0x00400000
UILAYER = 0x00500000
CODE_LO, CODE_HI = 0x3a0000, 0x3e0000
GAMENET_OFF = 0x6ac            # UILayer->gameNet offset (literal at 0x3c1ce4)

MEMORY_ITEM = 343
PENDING = GN + 0x0e
SENDBUF = GN + 0x0c
RECVBUF = GN + 0x200c

fail = 0
def check(cond, msg):
    global fail
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        fail += 1


def stub_return(uc, addr, size, user):
    if (addr & ~1) == BOX_STOP:
        uc.emu_stop()


def build(request_type=21, level=5, mode=2):
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    mu.mem_map(GN, 0x10000)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(RET & ~0xFFF, 0x1000)
    mu.mem_map(PI, 0x10000)
    mu.mem_map(UILAYER, 0x10000)
    mu.mem_map(CODE_LO, CODE_HI - CODE_LO)
    mu.mem_write(CODE_LO, d[CODE_LO:CODE_HI])
    # stubs
    mu.mem_write(PI_GET, bytes([0x00, 0x48, 0x70, 0x47]) + struct.pack('<I', PI))
    mu.mem_write(PI_SAVE, bytes([0x70, 0x47]))
    mu.mem_write(DISCONNECT, bytes([0x70, 0x47]))
    # fresh GameNet: pending request + arguments
    mu.mem_write(GN, b'\x00' * 0x10000)
    mu.mem_write(PENDING, bytes([request_type]))
    mu.mem_write(SENDBUF + 7, struct.pack('>I', level))
    mu.mem_write(SENDBUF + 11, struct.pack('>I', mode))
    mu.reg_write(UC_ARM_REG_SP, STACK + 0x8000)
    mu.reg_write(UC_ARM_REG_R0, GN)
    mu.reg_write(UC_ARM_REG_LR, RET | 1)
    mu.emu_start(RESPONDER | 1, RET, count=200000)
    return mu


print('--- step 1: responder synthesises the reward reply ---')
mu = build()
rb = bytes(mu.mem_read(RECVBUF, 32))
check(rb[0] == 22 and rb[1] == 0, f'reply type {rb[0]}, result {rb[1]} (expect 22 / 0)')
slot = struct.unpack('>I', rb[2:6])[0]
item = struct.unpack('>I', rb[6:10])[0]
gnd = struct.unpack('>I', rb[10:14])[0]
check(0 <= slot < 6, f'box slot {slot} within the 6-slot array')
check(item == MEMORY_ITEM, f'item type {item} == {MEMORY_ITEM} (Piece of Memory)')
check(gnd == 5, f'ground level {gnd} echoed from the request')

print('--- step 2: the real reply-22 handler consumes it ---')
# UILayer->gameNet must point at our GameNet
mu.mem_write(UILAYER + GAMENET_OFF, struct.pack('<I', GN))
# all 6 box slots start free (negative first dword); +0x7A0 must be a sane index
mu.mem_write(PI, b'\xa5' * 0x10000)
mu.mem_write(PI + 0x7A0, struct.pack('<i', 0))
mu.hook_add(UC_HOOK_CODE, stub_return)
mu.reg_write(UC_ARM_REG_SP, STACK + 0x8000)
mu.reg_write(UC_ARM_REG_R4, UILAYER)          # r4 = this (UILayer)
mu.reg_write(UC_ARM_REG_R5, GAMENET_OFF)
mu.reg_write(UC_ARM_REG_R6, GAMENET_OFF)
mu.reg_write(UC_ARM_REG_LR, RET | 1)
mu.emu_start(HANDLER | 1, RET, count=1000000)

base = PI + 0x23C + 12 * slot
w0 = struct.unpack('<i', bytes(mu.mem_read(base + 0, 4)))[0]
w1 = struct.unpack('<i', bytes(mu.mem_read(base + 4, 4)))[0]
w2 = struct.unpack('<i', bytes(mu.mem_read(base + 8, 4)))[0]
check(w0 == MEMORY_ITEM, f'ProgressInfo box slot {slot} type written = {w0} (expect {MEMORY_ITEM})')
check(w1 == gnd, f'ProgressInfo box slot {slot} ground level = {w1} (expect {gnd})')
check(w2 == -1, f'ProgressInfo box slot {slot} third dword = {w2} (expect -1)')
# no other slot may have been touched
others = []
for i in range(6):
    if i == slot:
        continue
    v = struct.unpack('<i', bytes(mu.mem_read(PI + 0x23C + 12 * i, 4)))[0]
    if v != -0x5A5A5A5B:                       # 0xA5A5A5A5 as signed
        others.append((i, v))
check(not others, f'other slots untouched ({others})')

print('--- step 3: a full box array must fall back to slot 0, not run off the end ---')
mu = build()
mu.mem_write(UILAYER + GAMENET_OFF, struct.pack('<I', GN))
mu.mem_write(PI, b'\x00' * 0x10000)            # every slot "occupied" (first dword 0)
mu.hook_add(UC_HOOK_CODE, stub_return)
mu.reg_write(UC_ARM_REG_SP, STACK + 0x8000)
mu.reg_write(UC_ARM_REG_R4, UILAYER)
mu.reg_write(UC_ARM_REG_R5, GAMENET_OFF)
mu.reg_write(UC_ARM_REG_R6, GAMENET_OFF)
mu.reg_write(UC_ARM_REG_LR, RET | 1)
mu.emu_start(HANDLER | 1, RET, count=1000000)
w0 = struct.unpack('<i', bytes(mu.mem_read(PI + 0x23C, 4)))[0]
check(w0 == MEMORY_ITEM, f'fell back to slot 0 (got {w0})')

ECONOMY = d[0x399454:0x399458] == bytes.fromhex('012225e0')
ECONOMY = d[0x399454:0x399458] == bytes.fromhex('012225e0')
print(f'--- step 4: ad trampoline (present in this build: {ECONOMY}) ---')
if not ECONOMY:
    print('  SKIP  the conservative build leaves the dead ad SDK path untouched')
else:
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    mu.mem_map(0x00390000, 0x10000)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(RET & ~0xFFF, 0x1000)
    mu.mem_write(0x00390000, d[0x00390000:0x003a0000])
    seen = {}

    def trace(uc, addr, size, user):
        if (addr & ~1) == 0x3994a4:
            seen['r2'] = uc.reg_read(UC_ARM_REG_R2)
            seen['sp'] = uc.reg_read(UC_ARM_REG_SP)
            uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, trace)
    sp0 = STACK + 0x8000
    mu.reg_write(UC_ARM_REG_SP, sp0)
    mu.reg_write(UC_ARM_REG_R2, 0)
    mu.reg_write(UC_ARM_REG_LR, RET | 1)
    mu.emu_start(0x399454 | 1, RET, count=1000)
    check(seen.get('r2') == 1, f'ad trampoline sets r2 = 1 (got {seen.get("r2")})')
    check(seen.get('sp') == sp0, f'ad trampoline consumes no stack (SP {seen.get("sp"):#x} vs {sp0:#x})')

    print('--- step 5: the 600-coin box cost literal must be neutralised ---')
    cost = struct.unpack('<i', d[0x3c1ce8:0x3c1cec])[0]
    check(cost == 0, f'the reply-14 cost literal is {cost} (expect 0)')

print()
print('RESULT:', 'ALL PASS' if fail == 0 else f'{fail} FAILURE(S)')
sys.exit(1 if fail else 0)
