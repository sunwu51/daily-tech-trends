# Daily Tech Trends

每天采集过去 24 小时的技术动态，再由 Codex 阅读原始来源，生成中文 AI 策展报告。报告按日期归档，GitHub 既有项目只有在本地快照观察到实际增长后，才会被标记为上升趋势。

## 项目结构

- `outputs/tech_trend_report.py`：采集 GitHub、Hacker News 和官方 RSS。
- `outputs/build_index.py`：扫描所有日期报告并更新根目录 `index.html`。
- `outputs/tech-trend-candidates.json`：供 Codex 筛选的候选证据，不是最终报告。
- `outputs/tech-trend-history.sqlite3`：GitHub Stars/Forks 历史基线，请持续保留。
- `outputs/tech-trends-raw.html`：脚本生成的原始预览。
- `outputs/tech-trends-YYYY-MM-DD.html`：Codex 整理后的每日中文报告。
- `outputs/tech-trends.html`：跳转到最新一期报告的固定入口。

## 手工采集

在项目根目录运行：

```powershell
python .\outputs\tech_trend_report.py --output .\outputs\tech-trends-raw.html --candidates-output .\outputs\tech-trend-candidates.json
```

脚本只负责收集与评分。最终中文报告必须由 Codex 阅读入选条目的原始来源后编写，不能直接发布原始预览。

## 在 Codex 中创建每日任务

1. 在 Codex Desktop 中将 `C:\Users\sunwu\Desktop\code\daily-tech-trends` 打开为本地项目。
2. 在这个新项目中创建定时任务，运行时间设为每天 08:00，时区使用 Asia/Shanghai。
3. 使用下面的完整提示词。
4. 本地任务运行时，电脑需要保持开机，Codex Desktop 需要保持运行。

### 定时任务提示词

```text
Every day, create a Chinese AI-curated technology trend report for the previous 24 hours in the current local project.

1. Confirm that the current project directory is `C:\Users\sunwu\Desktop\code\daily-tech-trends`. Determine the report date in China Standard Time as YYYY-MM-DD. Run `outputs/tech_trend_report.py --output outputs/tech-trends-raw.html --candidates-output outputs/tech-trend-candidates.json` to collect sources and update the GitHub history baseline. The raw preview must never be the final report.
2. Read `outputs/tech-trend-candidates.json`. It is evidence only, not a final report. Do not promote existing GitHub repositories unless their type is `project_rising`, and clearly distinguish `project_new` from observed growth.
3. Select exactly 10 substantive items whenever the candidate set contains 10 readable, technically meaningful sources. Treat 10 items as the daily target, not merely a maximum: after deduplication, expand across different technical areas and continue down the ranked candidates to fill every open slot with a verifiable secondary signal or early-stage item. Prioritize technical substance, independently corroborated discussion, actual measured GitHub growth, official releases, and engineering impact. Do not include a topic merely because it has a high score.
4. Before finalizing the selection, read every dated report from the previous 7 report dates that exists under `outputs/tech-trends-YYYY-MM-DD.html`. Do not repeat an item if its normalized primary URL, GitHub `owner/repository`, or underlying topic already appeared in those reports. Ignore URL fragments, tracking query parameters, and trailing slashes when comparing URLs. Routine additional Stars, Forks, commits, pushes, or continued discussion are not sufficient reasons to repeat an item. Repeat a previously covered item only when there is a substantive new event such as a new release, security incident, material technical change, or official announcement; in that case, state what changed since the earlier report and link to the new primary evidence.
5. For each selected item, open its primary URL and read the source material before writing. Do not infer claims from its title or raw summary. If the primary source cannot be read, omit it rather than guessing.
6. Write the polished Chinese report to `outputs/tech-trends-YYYY-MM-DD.html`, replacing YYYY-MM-DD with the report date. Include a Chinese title, a concise editorial overview, and for every selected item: what happened, the core technical point, why it matters, evidence/source links, and a clear maturity or risk note. Keep raw metrics as supporting evidence, not the headline. Include a brief "值得继续观察" section for weaker early signals when needed to reach the 10-item target. The combined number of main and early-signal items should be exactly 10 whenever 10 readable candidates remain after the 7-day deduplication; only publish fewer than 10 when fewer than 10 candidates can be verified, and state that shortfall explicitly in the report.
7. Update `outputs/tech-trends.html` into a lightweight HTML redirect/link to that exact dated report so it remains the latest-report entry point. Do not overwrite reports from earlier dates. Then run `python outputs/build_index.py` to refresh the root `index.html` archive page.
8. Publish the new report to GitHub Pages: stage only `index.html`, `outputs/tech-trends.html`, and the new dated report; commit them with a concise date-specific message that follows the repository's commit-message instructions; then push `main`. Do not commit the raw preview, candidate JSON, or SQLite history baseline. If there is nothing new to commit, do not create an empty commit.
9. State source outages, execution failures, or publication failures in the final task response, along with the generated dated report link. Do not use an external OpenAI API key; use the Codex task's own reasoning and browser/document-reading tools.
```

## GitHub Pages

根目录 `index.html` 提供全部日期报告的索引。推送到 `main` 后，`.github/workflows/pages.yml` 只发布索引、最新报告入口和日期报告，不发布候选数据或 GitHub 历史数据库。

## GitHub Token（可选）

GitHub 未认证搜索存在较低的速率限制。需要提高采集覆盖率时，可设置只读公共仓库 Token：

```powershell
[Environment]::SetEnvironmentVariable('GITHUB_TOKEN', 'github_pat_...', 'User')
```

设置后重启 Codex Desktop，使后台任务读取新的用户环境变量。不要将 Token 写入仓库。

## 评分边界

候选分数由来源内归一化热度、时效性、跨来源信号和官方/研究来源权重组成，只用于排序。新建仓库标记为 `project_new`；既有仓库必须由 SQLite 历史快照观察到至少 `+3 Stars` 或 `+1 Fork`，才标记为 `project_rising`。分数和 Stars 均不代表技术正确性、生产成熟度或独立背书。
