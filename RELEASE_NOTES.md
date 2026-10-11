# Release notes

## v1.0 — offline restoration + Chinese localization + box economy

Based on the community restoration of *Darkness Survival* 1.1.29.

**Stability**
- Fixed the crash on entering the game: the local reply synthesiser used
  `push {r4, lr}` but returned with `bx lr`, so it clobbered `r4` (the caller's
  `this`, which `UILayer::networking()` keeps live across the call) and leaked
  8 bytes of stack every frame.
- `GameNet::GameNet()` now clears the pending-request byte, so uninitialised heap
  can no longer be mistaken for a queued request during startup.

**Offline network takeover**
- `GameNet::getNetworkStatus()` became a zero-latency responder: it answers the
  client's own requests (type T -> reply T+1) from the send buffer, so features
  that waited for the dead server complete locally.
- `UILayer::sendPacket()`, `ZPPTCPNetwork::sendData*`, `UILayer::signIn()`
  neutralised accordingly.

**Box economy**
- Reply 22 now returns `result = 0` with a box payload, so defeating a boss /
  clearing an episode actually grants a memory item again. The previous build
  forced `result = 1`, which silently skipped every reward.
- The dead Unity Ads path tail-jumps straight to its completion handler.
- The 600 ancient-coin box cost literal is neutralised; achievement payout 100 -> 1000.

**Chinese localization**
- 1998 text-table entries, 123 UI/story strings in 38 `.csb` flatbuffers, and
  36 hard-coded room names in `.so` rodata.
- Simplified builds swap the subsetted Korean font for a 1415-glyph
  Noto Sans SC subset (OFL), which also shrinks the APK by ~2 MB.

**Verified**
- All patches are executed under Unicorn, including the real reply handlers for
  the box reward (reply 22), the ad box (28), the 600-coin box (14) and opening
  a box (10).
- Signatures verified with Google `apksig` (v1 + v2 + v3).

---

## Credits

Built with **DeepSeek Harness** ([`@deepseek-ai/dsh` 0.2.0-rc.2](https://github.com/deepseek-ai/deepseek-harness)), an agentic coding CLI driving
**DeepSeek** models. Base restoration by
[MichaelExperuim](https://github.com/MichaelExperuim/darkness-survival-restored);
original game © Zero++ Software, 2016.

---

## v1.1 — crash fixes, reference localization, quality repair

**Crash: tapping an unidentified item**
Four item records in the table at `0x85336c` (types 552, 576, 1114, 1138) hold
`0xBF800000` — the bit pattern of `-1.0f` — where a name-text id belongs.
`Item::getNameTextIDByItemType()` sends anything below -200 into
`GameData::getScrollIndex()`, which has **no bounds check**
(`ldr r0, [GameData + 4 + 4*(index+22)]`), so the read lands outside the heap.
Reproduced under Unicorn by executing the real `Item::getNameText()` for every
item type; fixed by setting those four records to `0`.

**Crash: tapping an equippable item**
`FontFreeType::renderCharAt` ran off the end of the glyph atlas with a garbage
`dest` pointer. Root cause: our own edits to the `.csb` layout files corrupted
the rich-text string feeding the atlas. The `.csb` files are now left untouched
(byte-identical to the base) and UI text is injected from the text table only.

**Chinese localization**
- Simplified only.
- One CJK font in **both** font slots.
- Text adopted from an existing fan localization, then repaired: 109 quality
  defects fixed (67 proper-noun / wrong-sense misreads, 35 dropped or invented
  meanings, 4 polarity flips, 2 typos, 1 wrong number), plus 5 data-corruption
  strings restored (a translator watermark replacing "Tap screen to start.", the
  game's own credits replaced by an advert, an antonym flip, two dropped zeros).
- Terminology normalised for a Western-fantasy register.

**Verification**
- `Item::getNameText()` swept over all 2600 item types — 0 faults.
- Real reply handlers executed under Unicorn for replies 22 / 28 / 14 / 10.
- Every translated string machine-checked: rich-text tag multiset and
  `%d`/`%s` specifiers identical to the English source, no Hangul, no
  Traditional-only characters, no length growth over the previous translation.
- All APKs verified with Google `apksig` (v1 + v2 + v3).
