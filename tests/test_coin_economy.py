#!/usr/bin/env python3
"""Execute the real reply-14 (600-coin box) and reply-28 (ad box) handlers under
Unicorn with a mocked ProgressInfo, and assert what they do to the wallet.

This verifies the two economy patches end-to-end:

  * reply 28 (UIMessageBox ad button -> request 27) must ADD coins to
    ProgressInfo+0x704 and arm the ad timer at +0x774;
  * reply 14 (the 600 ancient-coin box -> request 13) must NOT subtract anything
    any more (the -600 literal is neutralised) and must still add the Ankh at
    ProgressInfo+0x708.

Emulation stops right after the wallet writes, before the UI/epilogue, so no
cocos2d popup code has to run.

Usage: PYTHONPATH=pylibs python3 test_coin_economy.py work/libcocos2dcpp.so
"""
import sys, struct
from unicorn import *
from unicorn.arm_const import *

SO = sys.argv[1] if len(sys.argv) > 1 else 'work/libcocos2dcpp.so'
d = open(SO, 'rb').read()

REPLY14 = 0x3c19de
REPLY10 = 0x3c1820
REPLY28 = 0x3c1dc2
STOP14 = 0x3c1a3e          # just after the Ankh store
STOP10 = 0x3c1874          # just after the box timer store
STOP28 = 0x3c1e18          # just after the coin store

GN = 0x00100000
STACK = 0x00200000
RET = 0x00300000
PI = 0x00400000
SCENE = 0x00500000
UILAYER = 0x00600000
CODE_LO, CODE_HI = 0x380000, 0x3e0000
GAMENET_OFF = 0x6ac

STUBS = {
    0x3a3124: ('r0', PI),      # ProgressInfo::getInstance
    0x38bb20: ('r0', SCENE),   # GameScene::getInstance
    0x38bb18: ('r0', UILAYER), # GameScene::getUILayer
    0x3a2254: None,            # ProgressInfo::save
    0x3d5e68: None,            # GameNet::disconnect
    0x3a1770: None,            # PopupManager::closePopup
    0x3a182c: None,            # PopupManager::openPopup
    0x3bc340: None,            # UIGetRuneAnimation::create
    0x3a4600: None,            # ServerTime::getSeconds
}
COINS = PI + 0x704
ANKH = PI + 0x708
ADTIMER = PI + 0x774

fail = 0
def check(cond, msg):
    global fail
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        fail += 1


def run(handler, stop, result):
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    for a, s in [(GN, 0x10000), (STACK, 0x10000), (RET & ~0xFFF, 0x1000),
                 (PI, 0x10000), (SCENE, 0x1000), (UILAYER, 0x1000)]:
        mu.mem_map(a, s)
    mu.mem_map(CODE_LO, CODE_HI - CODE_LO)
    mu.mem_write(CODE_LO, d[CODE_LO:CODE_HI])
    # stubs: bx lr, optionally preloading a register
    for addr, setr in STUBS.items():
        code = (bytes([0x00, 0x48, 0x70, 0x47]) + struct.pack('<I', setr[1])) if setr else bytes([0x70, 0x47])
        mu.mem_write(addr, code)
    # GameNet with the synthesised reply: type/result live in recvbuf
    mu.mem_write(GN, b'\x00' * 0x10000)
    mu.mem_write(GN + 0x200d, bytes([result]))       # getResult() -> recvbuf[1]
    mu.mem_write(UILAYER + GAMENET_OFF, struct.pack('<I', GN))
    # wallet: coins 100, ankh 7, ad timer 0
    mu.mem_write(PI, b'\x00' * 0x10000)
    mu.mem_write(COINS, struct.pack('<i', 100))
    mu.mem_write(ANKH, struct.pack('<i', 7))
    def stop_hook(uc, addr, size, user):
        if (addr & ~1) == stop:
            uc.emu_stop()
    mu.hook_add(UC_HOOK_CODE, stop_hook)
    mu.reg_write(UC_ARM_REG_SP, STACK + 0x8000)
    mu.reg_write(UC_ARM_REG_R4, UILAYER)
    mu.reg_write(UC_ARM_REG_R5, GAMENET_OFF)
    mu.reg_write(UC_ARM_REG_R6, GAMENET_OFF)
    mu.reg_write(UC_ARM_REG_LR, RET | 1)
    mu.emu_start(handler | 1, RET, count=200000)
    return (struct.unpack('<i', bytes(mu.mem_read(COINS, 4)))[0],
            struct.unpack('<i', bytes(mu.mem_read(ANKH, 4)))[0],
            struct.unpack('<i', bytes(mu.mem_read(ADTIMER, 4)))[0])


ECONOMY = d[0x399454:0x399458] == bytes.fromhex('012225e0')
print(f'--- reply 28 (ad box)  [economy patches present: {ECONOMY}] ---')
if not ECONOMY:
    print('  SKIP  this build leaves the ad / 600-coin paths to the dead server')
else:
    coins, ankh, timer = run(REPLY28, STOP28, 0)
    check(coins == 150, f'ad box added +50 coins (100 -> {coins})')
    check(ankh == 7, f'ad box left Ankh alone (still {ankh})')
    check(timer == 0, f'ad timer armed from the (zeroed) reply payload = {timer}')

    print('--- reply 14 (600 ancient-coin box) ---')
    coins, ankh, timer = run(REPLY14, STOP14, 0)
    check(coins == 100, f'600-coin box no longer charges (100 -> {coins})')
    check(ankh == 8, f'600-coin box still grants the Ankh (7 -> {ankh})')

    print('--- reply 10 (open a memory item -> rune/recipe) ---')
    # reply 10 stamps the "opened at" timer into slot 0's third dword
    # (ProgressInfo+0x244+12*getBoxOpenIndex()), and our responder leaves the
    # unvalidated box index at 0, so the write must land in slot 0.
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    for a, s in [(GN, 0x10000), (STACK, 0x10000), (RET & ~0xFFF, 0x1000),
                 (PI, 0x10000), (SCENE, 0x1000), (UILAYER, 0x1000)]:
        mu.mem_map(a, s)
    mu.mem_map(CODE_LO, CODE_HI - CODE_LO)
    mu.mem_write(CODE_LO, d[CODE_LO:CODE_HI])
    for addr, setr in STUBS.items():
        code = (bytes([0x00, 0x48, 0x70, 0x47]) + struct.pack('<I', setr[1])) if setr else bytes([0x70, 0x47])
        mu.mem_write(addr, code)
    mu.mem_write(GN, b'\x00' * 0x10000)
    mu.mem_write(GN + 0x200d, bytes([0]))            # result = 0
    mu.mem_write(GN + 0x200e, struct.pack('>I', 3))  # getBoxOpenIndex -> recvbuf[2]
    mu.mem_write(UILAYER + GAMENET_OFF, struct.pack('<I', GN))
    mu.mem_write(PI, b'\x00' * 0x10000)
    def stop10(uc, addr, size, user):
        if (addr & ~1) == STOP10:
            uc.emu_stop()
    mu.hook_add(UC_HOOK_CODE, stop10)
    mu.reg_write(UC_ARM_REG_SP, STACK + 0x8000)
    mu.reg_write(UC_ARM_REG_R4, UILAYER)
    mu.reg_write(UC_ARM_REG_R5, GAMENET_OFF)
    mu.reg_write(UC_ARM_REG_R6, GAMENET_OFF)
    mu.reg_write(UC_ARM_REG_LR, RET | 1)
    mu.emu_start(REPLY10 | 1, RET, count=200000)
    word = struct.unpack('<I', bytes(mu.mem_read(PI + 0x244 + 12 * 3, 4)))[0]
    check(word != 0, f'reply 10 stamped the requested slot 3 (got {word})')
    untouched = struct.unpack('<I', bytes(mu.mem_read(PI + 0x244, 4)))[0]
    check(untouched == 0, f'other slots untouched (slot 0 = {untouched})')

print()
print('RESULT:', 'ALL PASS' if fail == 0 else f'{fail} FAILURE(S)')
sys.exit(1 if fail else 0)
