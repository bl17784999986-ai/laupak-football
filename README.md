# 竞彩足球赛前推盘预测模拟器（GitHub Actions 自动同步版）

## 上传与启用步骤
1. 将本压缩包解压后的所有文件（`index.html`、`data/matches.json`、`scripts/sync_jc_data.py`、`.github/workflows/sync.yml`）上传到你的 GitHub 仓库 `laupak-football` 根目录。
2. 进入仓库顶部的 **Actions** 选项卡，如果提示启用 Workflows，点击开启。
3. 之后每天北京时间 **07:00、12:00、18:00、22:00** 会自动同步最新赛程与赔率；你也可以随时在 **Actions → Sync Football JC Schedule & Odds → Run workflow** 手动点一次立即同步。
4. 在手机或电脑打开 `https://bl17784999986-ai.github.io/laupak-football/` 时，网页会自动读取仓库最新 `data/matches.json`（也可点击右上角「同步实时赔率」即时刷新）。
