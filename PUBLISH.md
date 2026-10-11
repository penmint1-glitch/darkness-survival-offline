# 发布到 GitHub 的步骤

本目录（`release/`）已经是一个**可以直接 `git init` 的仓库根目录**：328 KB，
只含文档、补丁脚本和测试，**不含任何 APK、也不含游戏本体**。

---

## 0. 先决定：要不要把 APK 放进仓库

| 方式 | 说明 |
|---|---|
| **推荐：APK 放 Releases** | 仓库保持几百 KB；APK 作为 release 附件（单个上限 2 GB）。参考项目就是这么做的。 |
| 直接 `git add *.apk` | 单个 79–81 MB，**没有超过 GitHub 100 MB 上限**，但 7 个约 560 MB，会把仓库历史撑爆，之后无法优雅地删除。**不建议。** |
| Git LFS | 可以，但 clone 需要 LFS 客户端；对只想下载 APK 的玩家反而更麻烦。 |

`release/.gitignore` 已经默认忽略 `apk/`、`work/`、`base/`、`*.apk`，
**避免把游戏本体或解包产物误传上去**。

---

## 1. 在 GitHub 网页上新建仓库

1. 打开 <https://github.com/new>
2. Repository name：例如 `darkness-survival-offline`
3. 选 Public（或 Private，之后可改）
4. **不要**勾选 "Add a README file"（本地已有）
5. Create repository

---

## 2. 本地初始化并提交

```bash
cd /home/pmtest/dsh-verify/release

git init -b main
git config user.name  "你的名字"
git config user.email "你的邮箱"

git add README.md RELEASE_NOTES.md SHA256SUMS.txt .gitignore docs tools tests
git status                 # 确认列表里没有任何 .apk / apk/ / work/
git commit -m "Darkness Survival offline patch: crash fix, offline network takeover, box economy, Chinese localization"
```

## 3. 关联远程并推送

```bash
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

推送时会要求认证。HTTPS 方式请用 **Personal Access Token**（GitHub 已不支持账号密码）：
Settings → Developer settings → Personal access tokens → Fine-grained token，
权限给 `Contents: Read and write`。

```bash
# 让 git 记住凭据（可选）
git config --global credential.helper store
```

---

## 4. 把 APK 作为 Release 附件上传

**建议用网页上传**：本机实测 `github.com` 与 `api.github.com` 可达，但
`objects.githubusercontent.com`（Release 附件走这个域名）**超时**，
命令行工具上传很可能会卡住。网页上传走浏览器，不受这个限制。

1. 仓库页 → 右侧 **Releases** → **Draft a new release**
2. **Choose a tag**：输入 `v1.0` → Create new tag
3. Release title：`v1.0 — 离线修复 + 中文化 + 箱子经济`
4. 描述里粘贴 `RELEASE_NOTES.md` 的内容
5. 把 5 个 APK 拖进 "Attach binaries"：

```
darkness_survival_offline_simplified.apk   ← 简体，推荐
darkness_survival_safe_simplified.apk      ← 简体，保守版
darkness_survival_offline.apk              ← 原版文本，完整离线
darkness_survival_safe.apk                 ← 原版文本，保守版
darkness_survival_baseline.apk             ← 零改动对照，仅排障用
```

6. 再把 `SHA256SUMS.txt` 也拖进去（方便玩家校验）
7. **Publish release**

> 有 `gh` CLI 的话等价命令是
> `gh release create v1.0 --title "..." --notes-file RELEASE_NOTES.md *.apk SHA256SUMS.txt`，
> 但本机 `gh` 未安装，且附件 CDN 不可达。

---

## 5. 发布前必须处理的三件事

1. **补上字体许可全文。**
   `docs/LICENSE-NotoSansSC.txt` 目前只是占位说明——简体版内置了 Noto Sans SC 的子集，
   OFL 1.1 要求随附许可全文。发布前执行：

   ```bash
   curl -L -o docs/LICENSE-NotoSansSC.txt \
     https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE
   ```

2. **确认没把游戏本体传上去。**
   ```bash
   git ls-files | grep -Ei '\.apk$|^apk/|^work/|^base/'   # 应当没有任何输出
   ```
   仓库里**不应该**有原始 APK、解包目录、或 `work/*.so`（那些都含游戏代码与素材）。

3. **脚本里的绝对路径。**
   `tools/` 里的脚本原本是在 `/home/pmtest/dsh-verify` 上开发的。
   `build_zh_apk.py` 我已经改成读环境变量 `BASE_APK` / `DS_ROOT` / `JAVA_HOME`，
   其余脚本（`apply_patches.py`、`dz.py`、`patch_csb.py`…）里仍有类似
   `apk/lib/armeabi/libcocos2dcpp.so` 的相对/绝对路径，公开前建议统一成
   命令行参数或环境变量，并在 README 里说明"需要自备基础 APK"。

---

## 6. 可选：加一个 CI 跑测试

`.github/workflows/test.yml`：

```yaml
name: tests
on: [push, pull_request]
jobs:
  unicorn:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install capstone unicorn
      # tests need a patched .so; build it from YOUR base APK first,
      # so either commit a fixture or skip this job.
      - run: PYTHONPATH=pylibs python3 tests/test_state_machine.py work/libcocos2dcpp.so
```

注意：测试需要一份打好补丁的 `.so` 才能跑，而那份 `.so` 含游戏代码，**不适合上传**。
所以 CI 要么只做 lint，要么让使用者自己提供基础 APK（用 repository secret 或手动触发）。

---

## 7. 法律与风险提示

- 原游戏 **© Zero++ Software, 2016**。这是非官方、非商业的保存性补丁，
  和参考项目
  [MichaelExperuim/darkness-survival-restored](https://github.com/MichaelExperuim/darkness-survival-restored)
  属同一性质。
- **重新分发 APK 意味着重新分发游戏本体**（虽然是打过补丁的）。这与参考项目做法一致，
  但严格来说仍处于版权灰色地带，权利人可以发 DMCA 要求下架。
- 如果你想把风险降到最低：**只发布 `tools/` + `docs/`（补丁脚本与说明），不发布 APK**，
  让使用者用自己的原版 APK 打补丁。README 里已经写了复现步骤。
- README 里已包含"如为权利人希望下架请提 issue"的声明。
