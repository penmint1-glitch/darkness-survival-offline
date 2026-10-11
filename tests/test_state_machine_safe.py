#!/usr/bin/env python3
"""Execute the WHITELIST (safe) responder under Unicorn and assert its contract.

The safe build answers only request 21 (prepareNewBox -> settlement) and 31
(prepareRequestAchievementReward -> achievements/Ancient Coins).  Every other
request must be consumed *without producing a reply*, so no other reply handler
can execute at all.

Usage: PYTHONPATH=pylibs python3 test_state_machine_safe.py work/libcocos2dcpp.safe.so
"""
import sys, struct
from unicorn import *
from unicorn.arm_const import *

SO = sys.argv[1] if len(sys.argv) > 1 else 'work/libcocos2dcpp.safe.so'
CODE_ADDR = 0x3d5d04
GN, STACK, RET = 0x00100000, 0x00200000, 0x00300000
PENDING = GN + 0x0e
SENDBUF = GN + 0x0c
RECVBUF = GN + 0x200c

data = open(SO, 'rb').read()
code = data[CODE_ADDR:CODE_ADDR + 204]

fail = 0
def check(cond, msg):
    global fail
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        fail += 1

ANSWERED = {21: 22, 31: 32}
PI = 0x00400000               # fake ProgressInfo object
PI_GET = 0x003a3124           # ProgressInfo::getInstance
PI_STUB = bytes([0x00, 0x48, 0x70, 0x47]) + struct.pack('<I', PI)
MEMORY_ITEM_PIECE = 343
R4_SENTINEL = 0x0BADF00D          # stands in for the caller's `this` pointer
SP_INIT = STACK + 0x8000

def run(pending_type, args=b'', heap_fill=b'\xa5'):
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    for a, s in [(0x100000, 0x10000), (0x200000, 0x10000), (0x300000, 0x1000),
                 (0x3d5000, 0x2000), (0x3a3000, 0x2000), (PI, 0x10000)]:
        mu.mem_map(a, s)
    mu.mem_write(PI_GET, PI_STUB)
    mu.mem_write(PI, b'\xa5' * 0x10000)      # negative -> all box slots free
    mu.mem_write(CODE_ADDR, code)
    mu.mem_write(GN, heap_fill * 0x10000)
    mu.mem_write(PENDING, bytes([pending_type]))
    if args:
        mu.mem_write(SENDBUF + 3, args)
    mu.reg_write(UC_ARM_REG_SP, SP_INIT)
    mu.reg_write(UC_ARM_REG_R0, GN)
    mu.reg_write(UC_ARM_REG_R4, R4_SENTINEL)
    mu.reg_write(UC_ARM_REG_LR, RET | 1)
    mu.hook_add(UC_HOOK_CODE, lambda uc, a, s, u: uc.emu_stop() if (a & ~1) == RET else None)
    mu.emu_start(CODE_ADDR | 1, RET, count=100000)
    r = mu.reg_read(UC_ARM_REG_R0)
    r = r - (1 << 32) if r >= (1 << 31) else r
    # Regression guard: the responder must restore r4 and SP (see patchdefs.py).
    check(mu.reg_read(UC_ARM_REG_R4) == R4_SENTINEL,
          f'[req {pending_type}] callee-saved r4 preserved')
    check(mu.reg_read(UC_ARM_REG_SP) == SP_INIT,
          f'[req {pending_type}] stack pointer balanced')
    return mu, r


print('--- idle ---')
mu, ret = run(0)
rb = bytes(mu.mem_read(RECVBUF, 32))
check(ret == -5, 'returns -5 ("packet ready") so no failure popup is created')
check(rb[0] == 0, 'no reply type -> UILayer::networking() dispatches nothing')
check(mu.mem_read(PENDING, 1)[0] == 0, 'pending flag clear')

print('--- every non-whitelisted request must be swallowed with NO reply ---')
for t in (1, 4, 5, 7, 9, 10, 11, 13, 15, 17, 19, 23, 25, 27, 29, 33, 35, 37, 39, 41, 42):
    mu, ret = run(t, bytes([0xde, 0xad, 0xbe, 0xef] * 4))
    rb = bytes(mu.mem_read(RECVBUF, 8))
    check(rb[0] == 0 and ret == -5 and mu.mem_read(PENDING, 1)[0] == 0,
          f'req {t:>2} -> no reply (type {rb[0]}), pending consumed')

print('--- the two whitelisted requests must be answered ---')
for t, exp in ANSWERED.items():
    mu, ret = run(t, bytes(range(16)))
    rb = bytes(mu.mem_read(RECVBUF, 8))
    check(rb[0] == exp, f'req {t} -> reply {rb[0]} (expect {exp})')
    check(mu.mem_read(PENDING, 1)[0] == 0, f'req {t} pending consumed exactly once')

print('--- reply 22 must GRANT a memory item for every box mode ---')
for mode in (0, 1, 2, 3):
    a_ = bytearray(16); a_[8:12] = struct.pack('>I', mode)
    a_[4:8] = struct.pack('>I', 7)              # arg1 = level -> sendbuf[7]
    mu, _ = run(21, bytes(a_))
    rb = bytes(mu.mem_read(RECVBUF, 32))
    idx = struct.unpack('>I', rb[2:6])[0]
    typ = struct.unpack('>I', rb[6:10])[0]
    gnd = struct.unpack('>I', rb[10:14])[0]
    check(rb[0] == 22 and rb[1] == 0,
          f'mode {mode} -> type {rb[0]}, result {rb[1]} (expect 22/0 = reward)')
    check(0 <= idx < 6 and typ == MEMORY_ITEM_PIECE and gnd == 7,
          f'mode {mode} -> slot {idx}, item {typ}, ground {gnd}')

print('--- reply 32 must carry result 0 (success) ---')
mu, _ = run(31, bytes(16))
rb = bytes(mu.mem_read(RECVBUF, 8))
check(rb[0] == 32 and rb[1] == 0, f'type {rb[0]}, result {rb[1]}')

print()
print('RESULT:', 'ALL PASS' if fail == 0 else f'{fail} FAILURE(S)')
sys.exit(1 if fail else 0)
