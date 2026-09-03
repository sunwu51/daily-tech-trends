# Daily Tech Trends

每天采集过去 24 小时的技术动态，再由 Codex 阅读原始来源，生成中文 AI 策展报告。当天报告会将 GitHub Trending Daily 的全语言与中文榜各前 10 项作为候选池，并在可验证时至少选入 4 个 GitHub Trending 项目；报告按日期归档。

## 项目结构

- `outputs/tech_trend_report.py`：采集 GitHub、Hacker News 和官方 RSS。
- `outputs/build_index.py`：扫描所有日期报告并更新根目录 `index.html`。
- `outputs/tech-trend-candidates.json`：供 Codex 筛选的候选证据，不是最终报告。
- `outputs/tech-trends-raw.html`：脚本生成的原始预览。
- `outputs/tech-trends-YYYY-MM-DD.html`：Codex 整理后的每日中文报告。
- `outputs/tech-trends.html`：跳转到最新一期报告的固定入口。

## 手工采集

在项目根目录运行：

```powershell
python .\outputs\tech_trend_report.py --output .\outputs\tech-trends-raw.html --candidates-output .\outputs\tech-trend-candidates.json
```

脚本只负责收集与评分。最终中文报告必须由 Codex 阅读入选条目的原始来源后编写，不能直接发布原始预览。

官方来源包括 Cloudflare、Google Developers、AWS、Kubernetes、Rust、GitHub Blog、Google Security、Microsoft Engineering、Netflix TechBlog、Meta Engineering、Mozilla Hacks、Python Insider、Go Blog、LLVM Releases、Docker、Grafana Labs 和 OpenAI News。每个 RSS 来源最多进入 3 条候选，RSS 候选总量最多 25 条；最终报告中同一机构最多 2 条。Anthropic 当前没有提供带可靠发布日期的官方 RSS，因此未使用第三方 Feed 或 sitemap 猜测发布时间。

## 每日 GitHub Action

`.github/workflows/daily-tech-trends.yml` 会在每天 **07:00 Asia/Shanghai** 自动运行（GitHub Actions 使用 UTC，因此 cron 为前一天 `23:00 UTC`），也可从 Actions 页面手动触发。手动运行时可填写 `report_date`（`YYYY-MM-DD`）；例如 `2026-09-03` 会以中国时间 `2026-09-02 07:00` 至 `2026-09-03 07:00` 为主要观察窗口，但允许当前 GitHub Trending、Hacker News 和近期高价值公告作为补充信号。它使用官方 `openai/codex-action` 运行 `.github/prompts/daily-tech-trends.md`，由 Codex 采集、阅读来源、编写报告并提交到 `main`；随后的 Pages 工作流会发布页面。

Codex 还通过 `.codex/config.toml` 加载 `https://orz-mcp.netlify.app/mcp` 这个远程 MCP，优先用于抓取公开网页、仓库 README 和文档，减少 Runner 上直接执行 `curl` 的网络/DNS问题。

在仓库 **Settings -> Secrets and variables -> Actions** 中配置：

| 类型 | 名称 | 值 |
| --- | --- | --- |
| Secret | `CODEX_API_KEY` | 自定义 Codex/Responses 服务的 token |
| Variable | `CODEX_BASE_URL` | 完整的 Responses API 地址，例如 `https://api.example.com/v1/responses` |
| Variable | `CODEX_MODEL` | 要使用的模型名，例如服务商提供的 `gpt-5-codex` |

`CODEX_BASE_URL` 必须是服务实际接收 `POST /responses` 的完整地址，不能只填写域名或 `/v1`。token 仅通过 Secret 传给 Action，不会写入提交、报告或日志。

日报由 Actions 的 `GITHUB_TOKEN` 推送，提交作者为 `github-actions[bot]`。这是自动化任务的独立身份，并不需要或使用个人 GitHub Token。

工作流已申请 `contents: write`，因此可直接推送到 `main`。若仓库为受保护分支，请在分支保护规则中允许 GitHub Actions 写入，或不要要求该分支只能经由 Pull Request 合并。Pages 工作流也会在日报工作流成功结束后运行；这是必要的，因为 `GITHUB_TOKEN` 创建的 push 不会触发其他 `push` 工作流。

## GitHub Pages

根目录 `index.html` 提供全部日期报告的索引。推送到 `main` 后，`.github/workflows/pages.yml` 只发布索引、最新报告入口和日期报告，不发布候选数据或 GitHub 历史数据库。

## GitHub Token（可选）

GitHub 未认证搜索存在较低的速率限制。需要提高采集覆盖率时，可设置只读公共仓库 Token：

```powershell
[Environment]::SetEnvironmentVariable('GITHUB_TOKEN', 'github_pat_...', 'User')
```

设置后重启 Codex Desktop，使后台任务读取新的用户环境变量。不要将 Token 写入仓库。

## 评分边界

候选分数由来源内归一化热度、时效性、跨来源信号和官方/研究来源权重组成，只用于排序。GitHub Trending Daily 的 “stars today” 是采集当时榜单的热度信号，不代表技术正确性、生产成熟度或独立背书。GitHub 和 Hacker News 的当前列表可作为补充信号，但补跑过去日期时不会将它们描述为历史榜单快照。
