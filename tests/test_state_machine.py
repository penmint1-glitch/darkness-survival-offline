#!/usr/bin/env python3
"""Execute the patched GameNet::getNetworkStatus() under Unicorn and assert behaviour."""
import sys, struct
from unicorn import *
from unicorn.arm_const import *

SO = sys.argv[1] if len(sys.argv) > 1 else 'work/libcocos2dcpp.so'
CODE_ADDR = 0x3d5d04          # getNetworkStatus entry (vaddr == file offset here)
GN = 0x00100000               # fake GameNet object
STACK = 0x00200000
RET = 0x00300000
PENDING = GN + 0x0e           # sendbuf[2]  = pending request type
SENDBUF = GN + 0x0c           # send buffer base
RECVBUF = GN + 0x200c         # receive buffer base
PI = 0x00400000               # fake ProgressInfo object
PI_GET = 0x003a3124           # ProgressInfo::getInstance
# stub that returns our fake ProgressInfo*:  ldr r0,[pc,#0] ; bx lr ; .word PI
PI_STUB = bytes([0x00, 0x48, 0x70, 0x47]) + struct.pack('<I', PI)

MEMORY_ITEM_PIECE = 343       # item type the responder grants on reply 22

data = open(SO, 'rb').read()
code = data[CODE_ADDR:CODE_ADDR + 204]

fail = 0


def check(cond, msg):
    global fail
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        fail += 1


R4_SENTINEL = 0x0BADF00D          # stands in for the caller's `this` pointer
SP_INIT = STACK + 0x8000


def run(pending_type, args=b'', label='', heap_fill=b'\xa5'):
    """args = 16 bytes to place at sendbuf[3] (the request payload area)."""
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    mu.mem_map(0x00100000, 0x10000)
    mu.mem_map(0x00200000, 0x10000)
    mu.mem_map(0x00300000, 0x1000)
    mu.mem_map(0x003d5000, 0x2000)
    mu.mem_map(0x003a3000, 0x2000)
    mu.mem_map(PI, 0x10000)
    mu.mem_write(PI_GET, PI_STUB)
    mu.mem_write(PI, b'\xa5' * 0x10000)          # 0xA5A5A5A5 is negative -> free slot
    mu.mem_write(CODE_ADDR, code)
    mu.mem_write(GN, heap_fill * 0x10000)          # mimic an un-zeroed heap block
    if pending_type is not None:
        mu.mem_write(PENDING, bytes([pending_type]))
    if args:
        mu.mem_write(SENDBUF + 3, args)
    mu.reg_write(UC_ARM_REG_SP, SP_INIT)
    mu.reg_write(UC_ARM_REG_R0, GN)
    mu.reg_write(UC_ARM_REG_R4, R4_SENTINEL)       # UILayer::networking() keeps `this` in r4
    mu.reg_write(UC_ARM_REG_LR, RET | 1)
    mu.hook_add(UC_HOOK_CODE, lambda uc, a, s, u: uc.emu_stop()
                if (a & ~1) == RET else None)
    mu.emu_start(CODE_ADDR | 1, RET, count=100000)
    r = mu.reg_read(UC_ARM_REG_R0)
    # Regression guard: `push {r4, lr}` must be undone before returning.  Leaking
    # either one corrupts UILayer::networking() and crashes the game on entry.
    check(mu.reg_read(UC_ARM_REG_R4) == R4_SENTINEL,
          f'[{label}] callee-saved r4 preserved (got {mu.reg_read(UC_ARM_REG_R4):#x})')
    check(mu.reg_read(UC_ARM_REG_SP) == SP_INIT,
          f'[{label}] stack pointer balanced (got {mu.reg_read(UC_ARM_REG_SP):#x})')
    return mu, r - (1 << 32) if r >= (1 << 31) else r


print('--- idle (no pending request) ---')
mu, ret = run(0, label='idle')
rb = bytes(mu.mem_read(RECVBUF, 32))
check(ret == -5, 'returns -5 ("packet ready")')
check(rb[0] == 0, 'recvbuf[0] == 0 -> getPacketType() 0 -> no dispatch')
check(rb[1] == 0, 'recvbuf[1] == 0 (result = success)')
check(all(b == 0 for b in rb[2:32]), 'reply payload fully zeroed (no stale heap bytes)')
check(mu.mem_read(PENDING, 1)[0] == 0, 'pending flag still clear')

print('--- pending login (type 0) must be ignored ---')
mu, ret = run(0, label='login')
rb = bytes(mu.mem_read(RECVBUF, 4))
check(rb[0] == 0, 'login is never answered (type 0 collides with the sentinel)')

print('--- pending sign-in (type 7) -> reply 8 ---')
mu, ret = run(7, label='signin')
rb = bytes(mu.mem_read(RECVBUF, 8))
check(ret == -5, 'returns -5')
check(rb[0] == 8, f'recvbuf[0] == 8 (got {rb[0]})')
check(rb[1] == 0, 'recvbuf[1] == 0 (success)')
check(mu.mem_read(PENDING, 1)[0] == 0, 'pending flag consumed')

print('--- achievement claim (type 31) -> reply 32, keyed by the claimed id ---')
args = bytes.fromhex('11223344' '00000005' '00000000' '00000000')   # sendbuf[3] = key, sendbuf[7] = id 5 (big-endian, as setPacketInt writes)
mu, ret = run(31, args)
rb = bytes(mu.mem_read(RECVBUF, 32))
check(rb[0] == 32, f'recvbuf[0] == 32 (got {rb[0]})')
check(rb[1] == 0, 'recvbuf[1] == 0 (success)')
check(rb[2:6] == b'\x00' * 4, 'achievement reply payload is NOT echoed (id comes from getAchievementId)')

print('--- new box (type 21) -> reply 22 must GRANT a memory item ---')
for mode in (0, 1, 2, 3):
    a_ = bytearray(16)
    a_[8:12] = struct.pack('>I', mode)         # arg2 lands at sendbuf[11]
    a_[4:8] = struct.pack('>I', 5)             # arg1 = level, lands at sendbuf[7]
    mu, ret = run(21, bytes(a_))
    rb = bytes(mu.mem_read(RECVBUF, 32))
    idx = struct.unpack('>I', rb[2:6])[0]
    typ = struct.unpack('>I', rb[6:10])[0]
    gnd = struct.unpack('>I', rb[10:14])[0]
    check(rb[0] == 22 and rb[1] == 0,
          f'mode {mode} -> type {rb[0]}, result {rb[1]} (expect 22/0 = reward granted)')
    check(0 <= idx < 6, f'mode {mode} box slot index in range (got {idx})')
    check(typ == MEMORY_ITEM_PIECE, f'mode {mode} item type = Piece of Memory (got {typ})')
    check(gnd == 5, f'mode {mode} ground level echoed from request (got {gnd})')

print('--- open box (type 9): reply 10 must NOT trust the unvalidated box-slot arg ---')
mu, ret = run(9, bytes.fromhex('00000000' '00000004' '00000000' '00000000'))
rb = bytes(mu.mem_read(RECVBUF, 32))
check(rb[0] == 10, f'recvbuf[0] == 10 (got {rb[0]})')
check(rb[2:6] == b'\x00' * 4, f'box slot NOT echoed, stays 0 (got {rb[2:6].hex()})')

print('--- rune level-up (type 17) -> reply 18 echoes 3 argument dwords ---')
mu, ret = run(17, bytes.fromhex('00000000' '00000007' '00000002' '00000001'))
rb = bytes(mu.mem_read(RECVBUF, 16))
check(rb[0] == 18, f'recvbuf[0] == 18 (got {rb[0]})')
check(rb[2:6] == struct.pack('>I', 7), f'rune index echoed: {rb[2:6].hex()} (expect 00000007)')
check(rb[6:10] == struct.pack('>I', 2), f'level echoed: {rb[6:10].hex()} (expect 00000002)')
check(rb[10:14] == struct.pack('>I', 1), f'count echoed: {rb[10:14].hex()} (expect 00000001)')

print('--- recipe level-up (type 19) -> reply 20 echoes 3 argument dwords ---')
mu, ret = run(19, bytes.fromhex('00000000' '00000009' '00000003' '00000002'))
rb = bytes(mu.mem_read(RECVBUF, 16))
check(rb[0] == 20 and rb[2:6] == struct.pack('>I', 9), f'reply 20 with echoed index ({rb[0]}, {rb[2:6].hex()})')

print('--- a request must fire exactly once ---')
mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
mu.mem_map(0x00100000, 0x10000); mu.mem_map(0x00200000, 0x10000)
mu.mem_map(0x00300000, 0x1000); mu.mem_map(0x003d5000, 0x2000)
mu.mem_map(0x003a3000, 0x2000); mu.mem_map(PI, 0x10000)
mu.mem_write(PI_GET, PI_STUB); mu.mem_write(PI, b'\xa5' * 0x10000)
mu.mem_write(CODE_ADDR, code); mu.mem_write(GN, b'\xa5' * 0x10000)
mu.mem_write(PENDING, bytes([21]))
mu.mem_write(SENDBUF + 11, struct.pack('>I', 1))
mu.reg_write(UC_ARM_REG_SP, SP_INIT); mu.reg_write(UC_ARM_REG_R0, GN)
mu.reg_write(UC_ARM_REG_R4, R4_SENTINEL)
mu.reg_write(UC_ARM_REG_LR, RET | 1)
mu.hook_add(UC_HOOK_CODE, lambda uc, a, s, u: uc.emu_stop() if (a & ~1) == RET else None)
mu.emu_start(CODE_ADDR | 1, RET, count=100000)
first = mu.mem_read(RECVBUF, 2)
check(mu.reg_read(UC_ARM_REG_R4) == R4_SENTINEL and mu.reg_read(UC_ARM_REG_SP) == SP_INIT,
      'r4/SP balanced on the first call')
mu.reg_write(UC_ARM_REG_SP, SP_INIT); mu.reg_write(UC_ARM_REG_R0, GN)
mu.reg_write(UC_ARM_REG_R4, R4_SENTINEL)
mu.reg_write(UC_ARM_REG_LR, RET | 1)
mu.emu_start(CODE_ADDR | 1, RET, count=100000)
second = mu.mem_read(RECVBUF, 2)
check(mu.reg_read(UC_ARM_REG_R4) == R4_SENTINEL and mu.reg_read(UC_ARM_REG_SP) == SP_INIT,
      'r4/SP balanced on the second call (no per-frame stack growth)')
check(first[0] == 22 and first[1] == 0, f'first call -> type {first[0]}, result {first[1]} (reward)')
check(second[0] == 0 and second[1] == 0, f'second call -> no reply (got {second[0]}/{second[1]})')

print('--- GameNet::GameNet() must clear the pending-request byte ---')
mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
mu.mem_map(0x00100000, 0x10000); mu.mem_map(0x00200000, 0x10000)
mu.mem_map(0x00300000, 0x1000); mu.mem_map(0x003d5000, 0x2000)
mu.mem_write(CODE_ADDR, code)
mu.mem_write(0x00100000 + 0x0e, b'\xff')          # pre-existing heap garbage
mu.reg_write(UC_ARM_REG_SP, STACK + 0x8000); mu.reg_write(UC_ARM_REG_R0, GN)
mu.reg_write(UC_ARM_REG_LR, RET | 1)
mu.hook_add(UC_HOOK_CODE, lambda uc, a, s, u: uc.emu_stop() if (a & ~1) == RET else None)
ctor = data[0x3d5ce0:0x3d5ce0 + 2]
mu.mem_write(0x3d5ce0, ctor)                        # the real patched ctor entry
mu.emu_start(0x3d5ce0 | 1, RET, count=1000)
state = struct.unpack('<I', bytes(mu.mem_read(GN, 4)))[0]
status = struct.unpack('<i', bytes(mu.mem_read(GN + 4, 4)))[0]
net = struct.unpack('<I', bytes(mu.mem_read(GN + 8, 4)))[0]
pend = mu.mem_read(PENDING, 1)[0]
check(state == 0, f'state = 0 (got {state})')
check(status == -6, f'status = -6 (got {status})')
check(net == 0, f'net = NULL (got {net})')
check(pend == 0, f'pending-request byte cleared (got {pend})')

print()
print('RESULT:', 'ALL PASS' if fail == 0 else f'{fail} FAILURE(S)')
sys.exit(1 if fail else 0)
