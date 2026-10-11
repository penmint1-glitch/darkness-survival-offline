#!/usr/bin/env python3
"""Byte patches for the Darkness Survival offline-network bypass.

Central idea: instead of a dead TCP server, GameNet answers its own requests.
`GameNet::getNetworkStatus()` becomes a zero-latency responder run from the
game's per-frame poll:

  * recvbuf[0..127] is cleared       (GameNet's ctor does NOT clear the buffers)
  * if a request is pending (sendbuf[2] != 0):
      - recvbuf[0] = request type + 1    (the reply type the client expects)
      - recvbuf[1] = 0                   ("result 0" == success), except reply
        22 which needs 1 to take the "settle / advance" branch
      - request argument dwords are echoed into the reply payload where the
        handler must see the values it asked about
      - the pending flag is cleared      (each request answered exactly once)
  * always returns -5 ("packet ready") to UILayer::networking()

Login (request type 0) is deliberately never answered: `prepareLogin` writes 0
into sendbuf[2], which is also the "nothing pending" sentinel. Reply type 1 runs
`GameNet::getProgressInfo()`, which overwrites *and saves* the live save game
from the packet, so an all-zero synthetic login reply would wipe progress.
"""
from armenc import *
from asm import show, enc_bw, enc_b

GETNETWORKSTATUS = 0x3d5d04
GETGAMENETSTATE  = 0x3d5d00
GAMENET_CTOR     = 0x3d5ce0
SENDPACKET_JUMP  = 0x3c04c8
SIGNIN           = 0x3c0584
SENDDATA         = 0x3d861a
SENDDATAWZPP     = 0x3d8632
PROGRESSINFO_GET = 0x3a3124
GETPACKETINT     = 0x3d86de

GET_ACHIEVEMENT_ID     = 0x3d6e24
GET_ACHIEVEMENT_REWARD = 0x3d6e38
GET_NEWBOX_GETTYPE     = 0x3d6eec
GET_NEW_MEDAL_NUM      = 0x3d6f58
GET_IAP_MEDAL_NUM      = 0x3d6c04
GET_USER_ID            = 0x3d6430
GET_BOX_MEDAL_ADD      = 0x3d6860
GET_ADBOX_MEDAL_ADD    = 0x3d689c
GET_BOX_ANKH_ADD       = 0x3d6874
GET_MEDALBOX_ANKH_ADD  = 0x3d68b0

RUNE_COIN_STORE   = 0x3d6a0e
RECIPE_COIN_STORE = 0x3d6ace
RESUR_ANKH_STORE  = 0x3d7100
RESUR_COIN_STORE  = 0x3d7114

# --- offline box economy -----------------------------------------------------
AD_PRESENT_JNI = 0x399454     # NativeWrapper::presentUnityAdsJNI
AD_COMPLETED   = 0x3994a4     # Java_..._onUnityAdsCompleted(jboolean) -- reads only r2
MEDAL_BOX_COST = 0x3c1ce8     # u32 literal -600 used by the reply-14 (600-coin box) handler

R0, R1, R2, R3, R4 = R['r0'], R['r1'], R['r2'], R['r3'], R['r4']
R5, R6 = R['r5'], R['r6']

# Item type id of "Piece of Memory" (기억의 파편) in the game's 204-byte item table
# at 0x85336c.  The reply-22 handler feeds this straight into
# Item::getNameTextIDByItemType/Item::getIconFilenameByItemType, which do NOT
# bounds-check, so it must be a real type: 342 = Particle, 343 = Piece,
# 344 = Crystal of Memory.
MEMORY_ITEM = 343

# Ancient Coins granted per achievement claim (each achievement pays once).
ACHIEVEMENT_REWARD = 1000


WHITELIST_TYPES = (21, 31)   # prepareNewBox (settlement) and prepareRequestAchievementReward (achievements/coins)


def build_responder(whitelist=False):
    c = Code(GETNETWORKSTATUS)
    # r4 = recvbuf, r5 = `this` (GameNet*), r6 scratch.  Four registers keeps SP
    # 8-byte aligned for the nested ProgressInfo::getInstance() call below.
    c.op(push((1 << R4) | (1 << R5) | (1 << R6), lr=True), 'push {r4, r5, r6, lr}')
    c.op(movs(R5, 0), 'movs r5, #0')
    c.op(adds_reg(R5, R0, R5), 'adds r5, r0, r5')
    c.op(movs(R2, 0x20), 'movs r2, #0x20')
    c.op(lsls(R2, R2, 8), 'lsls r2, r2, #8')
    c.op(adds_imm(R2, 0xc), 'adds r2, #0xc')
    c.op(adds_reg(R4, R0, R2), 'adds r4, r0, r2')
    c.op(movs(R3, 0), 'movs r3, #0')
    c.op(movs(R1, 0), 'movs r1, #0')
    c.label('Lz')
    c.op(str_reg(R3, R4, R1), 'str r3, [r4, r1]')
    c.op(adds_imm(R1, 4), 'adds r1, #4')
    c.op(cmp_imm(R1, 0x80), 'cmp r1, ' + imm(0x80))
    c.branch('bcond', 'Lz', 'lt')
    c.op(ldrb_imm(R1, R0, 0xe), 'ldrb r1, [r0, ' + imm(0xe) + ']')
    if whitelist:
        # Conservative mode: answer only the two request types this restoration
        # targets.  Everything else is consumed without a reply, so no other
        # reply handler can run at all.
        c.op(cmp_imm(R1, 21), 'cmp r1, ' + imm(21))
        c.branch('bcond', 'Lok', 'eq')
        c.op(cmp_imm(R1, 31), 'cmp r1, ' + imm(31))
        c.branch('bcond', 'Lok', 'eq')
        c.op(strb_imm(R3, R0, 0xe), 'strb r3, [r0, ' + imm(0xe) + ']')
        c.branch('b', 'Lret')
        c.label('Lok')
    else:
        c.op(cmp_imm(R1, 0), 'cmp r1, #0')
        c.branch('bcond', 'Lret', 'eq')
    c.op(adds_imm(R1, 1), 'adds r1, #1')
    c.op(strb_imm(R1, R4, 0), 'strb r1, [r4]')
    c.op(strb_imm(R3, R0, 0xe), 'strb r3, [r0, ' + imm(0xe) + ']')
    # ---- Reply 22: grant the memory-item reward ----
    # result 0 makes the reply-22 handler take the reward path: it stores a new
    # memory item into the player's 6-slot box array at ProgressInfo+0x23C
    # (stride 12, checked by ProgressInfo::haveFreeBoxSpace) and shows the
    # UIGetCrystal popup.  The previous build forced result 1 ("just advance"),
    # which silently skipped every boss / episode-clear reward -- that is exactly
    # why no Box of Memories ever appeared.
    # Payload dwords are big-endian, matching ZPPTCPNetwork::getPacketInt().
    c.op(cmp_imm(R1, 22), 'cmp r1, ' + imm(22))
    c.branch('bcond', 'Lnores', 'ne')
    c.op(movs(R2, 0), 'movs r2, #0')
    c.op(strb_imm(R2, R4, 1), 'strb r2, [r4, #1]')           # result = 0 (success)
    c.branch('bl', 'pinfo')
    c.op(addw(R2, R0, 0x23C), 'addw r2, r0, ' + imm(0x23C))
    c.op(movs(R3, 0), 'movs r3, #0')
    c.label('Lscan')
    c.op(ldr_imm(R0, R2, 0), 'ldr r0, [r2]')
    c.op(cmp_imm(R0, 0), 'cmp r0, #0')
    c.branch('bcond', 'Lslot', 'lt')                          # negative == free slot
    c.op(adds_imm(R2, 12), 'adds r2, ' + imm(12))
    c.op(adds_imm(R3, 1), 'adds r3, #1')
    c.op(cmp_imm(R3, 6), 'cmp r3, #6')
    c.branch('bcond', 'Lscan', 'ne')
    c.op(movs(R3, 0), 'movs r3, #0')                          # full: reuse slot 0
    c.label('Lslot')
    c.op(addw(R1, R4, 2), 'addw r1, r4, #2')                  # &recvbuf[2]
    c.op(rev(R3, R3), 'rev r3, r3')
    c.op(str_imm(R3, R1, 0), 'str r3, [r1]')                  # box slot index
    c.op(movw(R0, MEMORY_ITEM), 'movw r0, ' + imm(MEMORY_ITEM))
    c.op(rev(R0, R0), 'rev r0, r0')
    c.op(str_imm(R0, R1, 4), 'str r0, [r1, #4]')              # item type
    c.op(addw(R2, R5, 0x13), 'addw r2, r5, ' + imm(0x13))     # &sendbuf[7]
    c.op(ldr_imm(R0, R2, 0), 'ldr r0, [r2]')
    c.op(str_imm(R0, R1, 8), 'str r0, [r1, #8]')              # ground level (echoed)
    c.branch('b', 'Lret')
    c.label('Lnores')
    # Echo the request argument dwords into the reply payload only for the two
    # level-up handlers, whose ProgressInfo writes are index-bounds-checked by the
    # game itself.  Reply 10 is deliberately NOT echoed: its box-slot index comes
    # from an unvalidated argument and indexes ProgressInfo unchecked.
    if whitelist:
        c.op(movs(R3, 0), 'movs r3, #0')
        c.op(cmp_imm(R3, 0), 'cmp r3, #0')
        c.branch('bcond', 'Lret', 'eq')
    else:
        c.op(movs(R3, 0), 'movs r3, #0')
        c.op(cmp_imm(R1, 18), 'cmp r1, ' + imm(18))
        c.branch('bcond', 'Lthree', 'eq')
        c.op(cmp_imm(R1, 20), 'cmp r1, ' + imm(20))
        c.branch('bcond', 'Lhave', 'ne')
        c.label('Lthree')
        c.op(movs(R3, 3), 'movs r3, #3')
        c.label('Lhave')
        c.op(cmp_imm(R3, 0), 'cmp r3, #0')
        c.branch('bcond', 'Lret', 'eq')
    c.op(addw(R2, R0, 0x13), 'addw r2, r0, ' + imm(0x13))   # &sendbuf[7]
    c.op(addw(R1, R4, 2), 'addw r1, r4, #2')                 # &recvbuf[2]
    c.label('Lc')
    c.op(ldr_imm(R0, R2, 0), 'ldr r0, [r2]')
    c.op(str_imm(R0, R1, 0), 'str r0, [r1]')
    c.op(adds_imm(R2, 4), 'adds r2, #4')
    c.op(adds_imm(R1, 4), 'adds r1, #4')
    c.op(subs_imm(R3, 1), 'subs r3, #1')
    c.branch('bcond', 'Lc', 'ne')
    c.label('Lret')
    c.op(movs(R0, 5), 'movs r0, #5')
    c.op(rsbs(R0, R0), 'rsbs r0, r0, #0')
    # MUST return through the matching pop: the body clobbers r4 (it holds the
    # caller's `this` -- UILayer::networking() keeps its own pointer in r4 across
    # this call) and `push {r4, lr}` moved SP.  Returning with `bx lr` leaves both
    # r4 and SP corrupted, which segfaults the caller on the very next frame and
    # grows the stack by 8 bytes per call until it overflows.
    c.op(pop((1 << R4) | (1 << R5) | (1 << R6), pc=True), 'pop {r4, r5, r6, pc}')

    # ---- helpers, in the dead tail of the original function ----
    c.label('coins')
    c.op(push(1 << R3, lr=True), 'push {r3, lr}')
    c.branch('bl', 'progressinfo')
    c.op(ldr_imm_wide(R0, R0, 0x704), 'ldr.w r0, [r0, ' + imm(0x704) + ']')
    c.op(pop(1 << R3, pc=True), 'pop {r3, pc}')
    c.label('coins5')
    c.op(push(1 << R3, lr=True), 'push {r3, lr}')
    c.branch('bl', 'progressinfo')
    c.op(ldr_imm_wide(R0, R0, 0x704), 'ldr.w r0, [r0, ' + imm(0x704) + ']')
    c.op(adds_imm(R0, 5), 'adds r0, #5')
    c.op(pop(1 << R3, pc=True), 'pop {r3, pc}')
    c.label('progkey')
    c.op(push(1 << R3, lr=True), 'push {r3, lr}')
    c.branch('bl', 'progressinfo')
    c.op(ldr_imm(R0, R0, 8), 'ldr r0, [r0, #8]')
    c.op(pop(1 << R3, pc=True), 'pop {r3, pc}')

    # GameNet::GameNet() replacement, reached by `b` from the real constructor.
    # The stock constructor leaves the 8192-byte send buffer untouched, and
    # `operator new` does not zero it.  getNetworkStatus() treats sendbuf[2] as
    # "a request is pending", so uninitialised heap here would dispatch a bogus
    # reply handler on the first frames.
    c.label('ctor')
    c.op(movs(R2, 6), 'movs r2, #6')
    c.op(movs(R3, 0), 'movs r3, #0')
    c.op(rsbs(R2, R2), 'rsbs r2, r2, #0')
    c.op(str_imm(R3, R0, 0), 'str r3, [r0]')
    c.op(str_imm(R2, R0, 4), 'str r2, [r0, #4]')
    c.op(str_imm(R3, R0, 8), 'str r3, [r0, #8]')
    c.op(strb_imm(R3, R0, 0xe), 'strb r3, [r0, ' + imm(0xe) + ']')
    c.op(BX_LR, 'bx lr')

    c.labels['progressinfo'] = PROGRESSINFO_GET
    c.labels['pinfo'] = PROGRESSINFO_GET
    return c


def tailcall(at, target, size):
    code = enc_bw(at, target)
    assert len(code) <= size
    return code + NOP * ((size - len(code)) // 2)


def const_getter(value, size, at):
    c = Code(at)
    c.op(movs(R0, value), f'movs r0, ' + imm(value))
    c.op(BX_LR, 'bx lr')
    ok, code = c.verify(f'const({value})')
    assert ok, f'const_getter({value}) failed verification'
    return code + NOP * ((size - len(code)) // 2)


def movw_const_getter(value, size, at):
    """Same as const_getter but for values > 255 (needs a 32-bit movw)."""
    c = Code(at)
    c.op(movw(R0, value), 'movw r0, ' + imm(value))
    c.op(BX_LR, 'bx lr')
    ok, code = c.verify(f'movw_const({value})')
    assert ok, f'movw_const_getter({value}) failed verification'
    assert len(code) <= size, (len(code), size)
    return code + NOP * ((size - len(code)) // 2)


def echo_arg_getter(off, size, at):
    c = Code(at)
    c.op(push(1 << R3, lr=True), 'push {r3, lr}')
    c.op(adds_imm(R0, 0xc), 'adds r0, #0xc')
    c.op(movs(R1, off), f'movs r1, ' + imm(off))
    c.op(movs(R2, 4), 'movs r2, #4')
    c.branch('bl', 'gpi')
    c.op(pop(1 << R3, pc=True), 'pop {r3, pc}')
    c.labels['gpi'] = GETPACKETINT
    ok, code = c.verify('echo_arg')
    assert ok, 'echo_arg_getter failed verification'
    assert len(code) <= size
    return code + NOP * ((size - len(code)) // 2)


def achievement_id_getter(size, at):
    """Echo the requested achievement id via byte-wise reads; clamp to 0..84.

    Uses ZPPTCPNetwork::getPacketInt (byte-wise) rather than an unaligned
    `ldr.w` on sendbuf+7.
    """
    c = Code(at)
    c.op(push(1 << R3, lr=True), 'push {r3, lr}')
    c.op(adds_imm(R0, 0xc), 'adds r0, #0xc')          # this -> sendbuf
    c.op(movs(R1, 7), f'movs r1, ' + imm(7))
    c.op(movs(R2, 4), 'movs r2, #4')
    c.branch('bl', 'gpi')
    c.op(cmp_imm(R0, 84), 'cmp r0, ' + imm(84))
    c.branch('bcond', 'Lok', 'le')
    c.op(movs(R0, 0), 'movs r0, #0')
    c.label('Lok')
    c.op(pop(1 << R3, pc=True), 'pop {r3, pc}')
    c.labels['gpi'] = GETPACKETINT
    ok, code = c.verify('achievement_id')
    assert ok, 'achievement_id_getter failed verification'
    assert len(code) <= size, (len(code), size)
    return code + NOP * ((size - len(code)) // 2)


def build_patches(whitelist=False):
    c = build_responder(whitelist)
    ok, resp = c.verify('getNetworkStatus')
    assert ok, 'responder failed self-verification'
    assert GETNETWORKSTATUS + len(resp) <= 0x3d5dd0, 'responder overflows'
    L = c.labels
    P = [
        (GAMENET_CTOR, bytes.fromhex('0622002352420360'), enc_b(GAMENET_CTOR, L['ctor']),
         'GameNet::GameNet() -> also clear sendbuf[2] (uninitialised heap would otherwise '
         'be read as a pending request type)'),
        (GETGAMENETSTATE, bytes.fromhex('00687047'), bytes.fromhex('02207047'),
         'GameNet::getGameNetState() -> always 2 so UILayer::networking() keeps polling'),
        (SENDPACKET_JUMP, bytes.fromhex('0368'), bytes.fromhex('08e0'),
         'UILayer::sendPacket() -> always send (was connect-only while state==0)'),
        (SENDDATAWZPP, None, bytes.fromhex('7047'),
         'ZPPTCPNetwork::sendDataWithZPPCoder() -> no-op (NULL-deref site)'),
        (SENDDATA, None, bytes.fromhex('7047'),
         'ZPPTCPNetwork::sendData() -> no-op'),
        (SIGNIN, None, bytes.fromhex('7047'),
         'UILayer::signIn() -> no-op (no bogus sign-in reply at startup)'),
        (GETNETWORKSTATUS, None, resp,
         'GameNet::getNetworkStatus() -> local zero-latency reply synthesiser'),
        (GET_ACHIEVEMENT_ID, None, achievement_id_getter(20, GET_ACHIEVEMENT_ID),
         'GameNet::getAchievementId() -> echo claimed id, clamped to 0..84'),
        (GET_ACHIEVEMENT_REWARD, None, movw_const_getter(ACHIEVEMENT_REWARD, 20, GET_ACHIEVEMENT_REWARD),
         f'GameNet::getAchievementReward() -> {ACHIEVEMENT_REWARD} Ancient Coins'),
        (GET_NEWBOX_GETTYPE, None, echo_arg_getter(11, 20, GET_NEWBOX_GETTYPE),
         'GameNet::getNewBoxGetType() -> echo request arg2 (settle vs advance)'),
        (GET_NEW_MEDAL_NUM, None, tailcall(GET_NEW_MEDAL_NUM, L['coins5'], 20),
         'GameNet::getNewMedalNum() -> current coins +5 (idempotent assignment)'),
        (GET_IAP_MEDAL_NUM, None, tailcall(GET_IAP_MEDAL_NUM, L['coins'], 20),
         'GameNet::getInAppBillingMedalNum() -> current coins (idempotent assignment)'),
        (GET_USER_ID, None, tailcall(GET_USER_ID, L['progkey'], 20),
         'GameNet::getUserId() -> current save key (idempotent assignment)'),
        (GET_BOX_MEDAL_ADD, None, const_getter(50, 20, GET_BOX_MEDAL_ADD),
         'GameNet::getBoxRewardMedalAdd() -> +50 Ancient Coins'),
        (GET_ADBOX_MEDAL_ADD, None, const_getter(50, 20, GET_ADBOX_MEDAL_ADD),
         'GameNet::getAdBoxRewardMedalAdd() -> +50 Ancient Coins'),
        (GET_BOX_ANKH_ADD, None, const_getter(1, 20, GET_BOX_ANKH_ADD),
         'GameNet::getBoxRewardAnkhAdd() -> +1 Ankh'),
        (GET_MEDALBOX_ANKH_ADD, None, const_getter(1, 20, GET_MEDALBOX_ANKH_ADD),
         'GameNet::getMedalBoxRewardAnkhAdd() -> +1 Ankh'),
        (RUNE_COIN_STORE, bytes.fromhex('f850'), NOP,
         'getRuneLevelAndCount() -> drop store of recvbuf[14] into Ancient Coins'),
        (RECIPE_COIN_STORE, bytes.fromhex('f850'), NOP,
         'getRecipeLevelAndCount() -> drop store of recvbuf[14] into Ancient Coins'),
        (RESUR_COIN_STORE, bytes.fromhex('f050'), NOP,
         'getResurrectionResult() -> drop store of recvbuf[6] into Ancient Coins'),
        (RESUR_ANKH_STORE, bytes.fromhex('f050'), NOP,
         'getResurrectionResult() -> drop store of recvbuf[2] into Ankh'),
        (AD_PRESENT_JNI, bytes.fromhex('30b5104c'), bytes.fromhex('012225e0'),
         'NativeWrapper::presentUnityAdsJNI() -> tail-call the ad-completed entry with r2=1; '
         'the Unity ad SDK is dead so the shop free-box button used to grant nothing'),
        (MEDAL_BOX_COST, bytes.fromhex('a8fdffff'), bytes.fromhex('00000000'),
         'reply-14 handler literal -600 -> 0 (the 600 ancient-coin box becomes free)'),
    ]
    if whitelist:
        keep = {GAMENET_CTOR, GETGAMENETSTATE, SENDPACKET_JUMP, SENDDATAWZPP, SENDDATA, SIGNIN,
                GETNETWORKSTATUS, GET_ACHIEVEMENT_ID, GET_ACHIEVEMENT_REWARD, GET_NEWBOX_GETTYPE}
        P = [x for x in P if x[0] in keep]
    return P, resp


import sys as _sys
PATCHES, RESP = build_patches('--whitelist' in _sys.argv)

if __name__ == '__main__':
    show(RESP, GETNETWORKSTATUS, 'new GameNet::getNetworkStatus() + helpers')
    print(f'\nresponder: {len(RESP)} bytes, ends 0x{GETNETWORKSTATUS + len(RESP):x} (limit 0x3d5dd0)\n')
    for off, orig, new, desc in PATCHES:
        if off == GETNETWORKSTATUS:
            continue
        show(new, off, desc)
        print()
