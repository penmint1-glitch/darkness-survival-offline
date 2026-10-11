# Darkness Survival — Offline Preservation Patch

[中文说明见下方](#中文说明)

An unofficial, non-commercial **preservation patch** for *Darkness Survival*
(Zero++ Software, 2016), an Android dungeon-crawler whose online backend has been
dead for years. It makes the game fully playable offline and adds a Simplified /
Traditional Chinese localization.

Built on top of the community restoration by
[@MichaelExperuim](https://github.com/MichaelExperuim/darkness-survival-restored)
(base version 1.1.29). All credit for the original restoration goes there.

---

## Downloads

Pick **one** APK. Names ending in `_simplified` are Simplified Chinese, `_zh` are
Traditional Chinese, no suffix is the original English/Korean text.

| File | Language | Network | Size | What it does |
|---|---|---|---|---|
| `darkness_survival_offline_simplified.apk` | Simplified Chinese | full offline takeover | 78.9 MB | **recommended** — every feature works: box economy, runes, recipes, resurrection |
| `darkness_survival_safe_simplified.apk` | Simplified Chinese | conservative | 78.9 MB | answers only boss boxes + achievements; smallest change surface |
| `darkness_survival_offline.apk` | original (English) | full offline takeover | 80.6 MB | same patches, untouched text **and** untouched fonts |
| `darkness_survival_safe.apk` | original (English) | conservative | 80.6 MB | same, conservative responder |
| `darkness_survival_baseline.apk` | original (English) | none | 80.6 MB | diagnostic only: unmodified native library, re-signed — isolates base-game bugs from patch bugs |

All builds need a device with 32-bit **`armeabi`** support — the game ships only
`lib/armeabi/libcocos2dcpp.so`. The Simplified builds are actually ~1.7 MB
*smaller* than the English ones, because the replaced font is a subset (see
[Fonts](#fonts)).

Checksums: [`SHA256SUMS.txt`](SHA256SUMS.txt). Signatures verified with Google's
own `apksig` (v1 + v2 + v3 = true).

## Installing

1. Uninstall any previous Darkness Survival (including the original) — this build
   is signed with a different key, so Android will refuse to install over it.
2. Copy the APK to the device, tap it, allow "install unknown apps" if asked.
3. Launch. It goes straight to the title screen; no "Connecting to the Server".

Requires Android with 32-bit `armeabi` support (the game ships only
`lib/armeabi/libcocos2dcpp.so`). Tested working on Android 14 / Origin OS.

## What was broken, and what this patch does

| Symptom | Cause | Fix |
|---|---|---|
| Hangs on "Connecting to the Server" | `UILayer::openConnectingServer()` builds a popup and blocks | first instruction → `bx lr` |
| Dead Google Play sign-in prompt | GPGS backend for a delisted app is gone | `NativeWrapperActivity.login()` → `return-void`; `GameHelper.onStart()` → unconditional goto to the graceful-failure path |
| In-game UI unresponsive | per-frame "connection failed" popup ate every touch | `GameNet::getNetworkStatus()` → local zero-latency reply synthesiser |
| App crashed right after entering the game | the responder did `push {r4,lr}` but returned with `bx lr`, corrupting `r4` (the caller's `this`) and leaking 8 bytes of stack per frame | responder now returns via `pop {r4,pc}` |
| Server-dependent features hung (settlement, achievements, box rewards) | request T is answered by the dead server with T+1 | client answers itself; only the flows that are safe are enabled per build |
| No Box of Memories after a boss | the reply-22 handler only stores the reward when `result == 0`; the patch had forced `result = 1` | reply 22 now returns `result = 0` with the box payload (free slot, memory item, ground level) |
| Free box via ads did nothing | the Unity Ads SDK no longer serves inventory, so the completion callback never fires | the JNI entry tail-jumps straight to the completion handler with `r2 = 1` |
| 600 ancient-coin box unobtainable | the coins could not be bought and the cost literal was `-600` | cost literal → `0`; achievement payout 100 → 1000 |
| Everything in Korean | no Chinese localization exists | 2978 text-table entries translated to Simplified Chinese (the `.csb` layouts are left untouched — their strings are runtime placeholders) |
| Crash when tapping an unidentified item | four item records carry the bit pattern `0xBF800000` (-1.0f) as their name-text id; `Item::getNameTextIDByItemType` routes anything < -200 into `GameData::getScrollIndex()`, which has no bounds check | those four records set to `0`, the value 848 other nameless records already use |
| Crash when tapping an **equippable** item (font atlas) | `FontFreeType::renderCharAt` ran off the end of the glyph atlas | the `.csb` layout files must **not** be touched — UI text is injected at runtime from the text table; the second font slot (`arial.ttf`) must carry a CJK font |

Full byte-level details: [`docs/PATCH_NOTES.md`](docs/PATCH_NOTES.md).

## Fonts

The Simplified builds bundle **one** font and install it into **both**
`assets/SeoulNamsanEB.ttf` and `assets/arial.ttf` (the game may render a given
label through either slot, and the original second slot had no CJK coverage at
all — that mismatch was the cause of a crash).

| | |
|---|---|
| Face | **Noto Sans SC** (Regular), subsetted — 1,520 glyphs kept out of 30,890 |
| Licence | **SIL Open Font License 1.1** — redistribution inside an application permitted |
| Upstream | <https://github.com/notofonts/noto-cjk> |
| Size | **325,884 bytes** per slot (3.9 % of the 8,331,336-byte original face); installed into both slots, so 651,768 bytes uncompressed in total |
| Coverage | every character in the text table and in the 330 Cocos Studio `.csb` layouts |
| Known gap | no Hangul. The native library has 379 Hangul syllables in hard-coded strings; those render blank. The English and Korean builds are unaffected. |

The subset was produced with `fontTools.subset` from the character set actually
used by the text table, the shipped `.csb` layouts, ASCII and the punctuation
above; coverage was then verified against the subset's cmap (0 missing for the
text table and for ASCII). The scripts are in `tools/`.

An earlier build bundled a commercial Founder face (FZHuaLi-M14, 方正华隶); it was
removed because redistributing it requires a paid licence. See
[`docs/LICENSE-FONT.txt`](docs/LICENSE-FONT.txt), which also records how to swap
the face via the `DS_FONT_DIR` environment variable.

## Chinese localization notes

The game ships a **subsetted** Korean face that only covers the 4888 KS-X Hanja
and Hangul, and its second slot (`arial.ttf`) has no CJK coverage at all — so a
Simplified translation cannot be rendered with the shipped fonts. Both slots are
therefore replaced (see [Fonts](#fonts)).

Text is translated in **one** place: the text table (`assets/textdata_*.dat`,
2978 entries). The Cocos Studio `.csb` layouts are **not** touched — see above.

## Reproducing

You need your own copy of the base APK — none is redistributed here.

```bash
# 1. byte patches into the native library
PYTHONPATH=pylibs python3 apply_patches.py <base>/lib/armeabi/libcocos2dcpp.so   # full build
PYTHONPATH=pylibs python3 apply_patches.py work/libcocos2dcpp.safe.so --whitelist # conservative

# 2. verify by executing the patched code
PYTHONPATH=pylibs python3 test_state_machine.py work/libcocos2dcpp.so
PYTHONPATH=pylibs python3 test_getters.py       work/libcocos2dcpp.so
PYTHONPATH=pylibs python3 test_box_reward.py    work/libcocos2dcpp.so
PYTHONPATH=pylibs python3 test_coin_economy.py  work/libcocos2dcpp.so

# 3. localization - the text table ONLY; never touch the .csb layouts
python3 tools/build_textdata.py ...        # apply the translations, keep the format
# (patch_csb.py and patch_so_strings.py are kept for reference but are NOT used:
#  editing .csb breaks the rich-text path, and the room-name strings are rodata)

# 4. repackage + sign
python3 zh/build_zh_apk.py work/libcocos2dcpp.sim.so work/textdata_sim.dat out.apk
```

Note: the scripts currently contain absolute paths from the machine they were
developed on; adjust them for your checkout.

## Verification performed

Nothing here is "read the disassembly and hope". Every patch is checked by
**executing the patched code** under Unicorn:

* `test_state_machine.py` / `test_state_machine_safe.py` — the reply synthesiser:
  reply mapping, never answering login, argument echoing, `r4`/`SP` restored on
  every call, conservative build answering only what it should.
* `test_getters.py` — currency-integrity getters (no wallet wipe).
* `test_box_reward.py` — feeds the synthesised reply 22 to the **real handler** and
  asserts the memory item lands in `ProgressInfo`'s 6-slot box array.
* `test_coin_economy.py` — runs the real reply-14/28/10 handlers and asserts the
  wallet effects (+50 ad coins, no 600 charge, box-open timestamp).

Packaging: 4-byte alignment of all STORED entries, `resources.arsc` untouched,
`classes.dex` / `AndroidManifest.xml` byte-identical to the base, signatures
verified by Google's `apksig`.

## Credits

Reverse engineering, the byte-level patches, the Unicorn verification harness and
the Chinese localization were all produced with **[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)**
([`@deepseek-ai/dsh` 0.2.0-rc.2](https://github.com/deepseek-ai/deepseek-harness),
an agentic coding CLI) driving **DeepSeek** models.

* **Base restoration:** [MichaelExperuim/darkness-survival-restored](https://github.com/MichaelExperuim/darkness-survival-restored)
* **Original game:** Darkness Survival, © Zero++ Software, 2016
* **Bundled font:** Noto Sans SC (full face, 30,890 glyphs), SIL Open Font License 1.1

## Legal

* Original game **© Zero++ Software, 2016**. All original assets, code and design
  remain the property of their creators. This is an unofficial, non-commercial
  preservation patch, not a re-release.
* Built on the community restoration by
  [MichaelExperuim](https://github.com/MichaelExperuim/darkness-survival-restored).
* The bundled `Noto Sans SC` font is licensed under the SIL Open Font License
  1.1; see `docs/LICENSE-FONT.txt` (the OFL text itself still needs to be added).
* If you are a rights holder and want this removed, open an issue.

---

## 中文说明

这是 *Darkness Survival*（Zero++ Software, 2016）**非官方、非商业的离线保存补丁**。
游戏服务器多年前已停运，本补丁让它在完全离线的情况下可玩，并加入**简体中文**。

基于 [MichaelExperuim](https://github.com/MichaelExperuim/darkness-survival-restored)
的社区修复版（1.1.29）。原修复版的所有功劳归其作者。

### 下载哪个

| 文件 | 语言 | 说明 | 体积 |
|---|---|---|---|
| `darkness_survival_offline_simplified.apk` | **简体中文** | **推荐**：完整离线接管，箱子经济/符文/配方/复活全部可用 | 78.9 MB |
| `darkness_survival_safe_simplified.apk` | 简体中文 | 保守版：只应答 Boss 记忆之箱与成就，改动面最小 | 78.9 MB |
| `darkness_survival_offline.apk` | 原版（英文） | 同样补丁，文本**与字体**均保持原样 | 80.6 MB |
| `darkness_survival_safe.apk` | 原版（英文） | 同上，保守版应答 | 80.6 MB |
| `darkness_survival_baseline.apk` | 原版（英文） | 仅重新签名、零改动，用于区分"原版 bug"与"补丁 bug" | 80.6 MB |

简体版反而比原版**小约 1.7 MB**——替换的字体是**子集**（1,520 字形，326 KB，见下文「字体」）。
所有版本都需要支持 32 位 **`armeabi`** 的设备（游戏只提供 `lib/armeabi/libcocos2dcpp.so`）。

### 安装

1. 先卸载旧的 Darkness Survival（含原版）——签名不同，无法覆盖安装。
2. 把 APK 传到手机，点击安装，按提示允许"安装未知应用"。
3. 启动后直接进标题画面，不再出现 "Connecting to the Server"。

需要设备支持 32 位 `armeabi`。已在 Android 14 上实测可运行。

### 主要修复

- 去掉启动时的 "Connecting to the Server" 网络门槛
- 禁用已失效的 Google Play Games 自动登录与手动登录
- 本地应答取代死掉的服务器（结算画面、成就、箱子奖励不再卡住）
- 修复"进入游戏即闪退"（应答函数栈/寄存器未还原）
- 恢复打完 Boss 的记忆之箱奖励；广告奖励可用；600 古代硬币箱子免费
- 全文中文化：**2978 条主文本**（只改文本表，`.csb` 布局一律不动）

### 说明

- 游戏自带字体是**子集字体**（仅 4888 个朝鲜汉字 + 韩文），第二个字体槽 `arial.ttf` 更是完全没有中日韩字形，
  因此简体版把**两个槽都换成 `Noto Sans SC` 子集**（保留 1,520 字形，326 KB，SIL OFL 1.1 许可）。
- 本仓库**不包含**原始游戏 APK，复现需要自备基础包。
- 原游戏 © Zero++ Software, 2016，本补丁仅供个人保存使用，非商业用途。

### 制作方式

本次的逆向分析、字节级补丁、Unicorn 验证工具链与全文中文化，均由
**[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)**（`@deepseek-ai/dsh` 0.2.0-rc.2，agentic 编码 CLI）
驱动 **DeepSeek** 模型完成。

- 基础修复版：[MichaelExperuim/darkness-survival-restored](https://github.com/MichaelExperuim/darkness-survival-restored)
- 原游戏：Darkness Survival，© Zero++ Software, 2016
- 内置字体子集：Noto Sans SC（SIL Open Font License 1.1）

---

## Chinese localization

Text lives in the **text table only** (2978 entries). The Cocos Studio `.csb`
layouts are left **byte-identical to the base** — their Korean strings are
placeholders that the game overwrites at runtime, and editing them corrupts the
rich-text path that fills the glyph atlas (that was the cause of a crash when
tapping an equippable item).

The font is a single CJK face — **Noto Sans SC** (SIL Open Font License 1.1) —
installed into **both** `assets/SeoulNamsanEB.ttf` and `assets/arial.ttf`, since
the game may render a given label through either slot. See [Fonts](#fonts).

String length is also constrained deliberately: the game formats text with a
hand-written **unbounded** `sprintf` into fixed caller stack buffers, so a
translation longer than the Korean original is a stack-overflow risk. 268 strings
that overshot were compressed back inside the Korean byte budget.

Terminology follows a Western-fantasy / tabletop register (精准度 Accuracy,
警戒陷阱 Alarm Trap, 毁灭护符 Amulet of Destruction, 奥术 Arcane, 镜像 Mirror
Image, 鉴定 Identify, 记忆之匣 Box of Memories). 109 machine-translation defects
inherited from the reference localization were repaired — see
`docs/translation_quality_fixes.md`.

## Credits

Reverse engineering, the byte-level patches, the Unicorn verification harness and
the Chinese localization were produced with **[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)**
(`@deepseek-ai/dsh`), an agentic coding CLI driving **DeepSeek** models.

* **Base restoration:** [MichaelExperuim/darkness-survival-restored](https://github.com/MichaelExperuim/darkness-survival-restored)
* **Reference localization:** the Simplified-Chinese text is adapted from a
  pre-existing fan translation (游乐园汉化), with its machine-translation errors
  repaired and its watermark/attribution strings removed. Its bundled font was a
  commercial Founder face and has been **replaced** with Noto Sans SC (OFL).
* **Original game:** Darkness Survival, © Zero++ Software, 2016
