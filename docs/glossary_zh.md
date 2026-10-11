# 简体中文术语表 (Korean/English -> 简体中文)

同一概念必须使用同一译名。

| 한국어 | English | 简体中文 |
|---|---|---|
| 던전 | Dungeon | 地牢 |
| 모험 / 모험가 | Adventure / Adventurer | 冒险 / 冒险者 |
| 어둠 / 암흑 | Darkness | 黑暗 |
| 지하 / 층 | Underground / Floor | 地下 / 层 |
| 룬 | Rune | 符文 |
| 제작법 | Recipe | 配方 |
| 고대의 주화 | Ancient Coin | 古代硬币 |
| 마법 | Magic | 魔法 |
| 몬스터 | Monster | 怪物 |
| 보스 | Boss | 首领 |
| 아이템 | Item | 道具 |
| 무기 | Weapon | 武器 |
| 방어구 | Armor | 防具 |
| 물약 | Potion | 药水 |
| 직업 | Class | 职业 |
| 스킬 | Skill | 技能 |
| 레벨 | Level | 等级 |
| 정신력 | Spirit | 灵魂 |
| 생명력 | Life | 生命 |
| 피로 | Fatigue | 疲劳 |
| 골드 | Gold | 金币 |
| 업적 | Achievement | 成就 |
| 전설 | Legend | 传说 |
| 운명 | Fate | 命运 |
| 예언 | Prophecy | 预言 |
| 부활 | Resurrection | 复活 |
| 함정 | Trap | 陷阱 |
| 확인 | Confirm / Identify | 确认 / 鉴定 |
| 상점 | Shop | 商店 |
| 저장 | Save | 存档 |
| 휴식 | Rest | 休息 |

---

## 参考包术语校准（本次）

依据 `heianshengc.apk`（同一游戏的原版 1.0.9 汉化版）做了逐条甄别，**采纳 257 条 / 拒绝 1320 条**。

上表三行按采纳结果改定：`Trap 机关→陷阱`、`Recipe 制作法→配方`、`Spirit 精神力→灵魂`。

其余值得记录的风格取向（更贴西幻 / D&D 语域）：

| 英文 | 采定 | 说明 |
|---|---|---|
| Accuracy | 精准度 | 取代「命中率」 |
| Arcane | 奥术 | D&D 经典译法（拒绝参考包的「奥数」误译） |
| Mirror Image | 镜像 | D&D 法术名 |
| Identify | 鉴定 | 取代「确认」 |
| Box of Memories | 记忆之匣 | 取代「记忆箱子」 |
| Box (reward) | 宝箱 / 匣 | 视语境 |
| Gladiator | 角斗士 | 取代「剑斗士」 |
| RUNES | 符文 | 去掉「持有信息」等冗词 |

**明确拒绝参考包的做法**（机翻错误，已记录 1320 条理由于 `zh/ref_curated.json`）：

- 专有名词误读：`Durandal → 空对地导弹`、`Aegis → 羊皮盾`、`Ambrosia → 豚草`、`Mimic → 变种`、`Kusanagi → 草剃`（且用错字）
- 第二义项直译：`Vacuum → 吸尘器`、`Staff → 次元管理员`、`Pack → 背包`
- 整句膨胀：把简短状态串改写成完整句子（+4 ~ +22 汉字），是本项目最大的崩溃风险来源
- 语义反转 / 数据错误：`invisible objects → 可见目标`、`Defeat 200000 → 打败20000`（丢了一个 0）
- 译者署名覆盖原文：`Tap screen to start. → 游乐园汉化出品`
