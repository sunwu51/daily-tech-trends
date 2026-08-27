#!/usr/bin/env python3
"""Build the public report index from dated HTML reports."""

from __future__ import annotations

import argparse
import html
import re
from datetime import datetime
from pathlib import Path


REPORT_RE = re.compile(r"tech-trends-(\d{4}-\d{2}-\d{2})\.html$")


def build_index(reports_dir: Path, output: Path) -> None:
    reports: list[tuple[datetime, Path]] = []
    for report in reports_dir.glob("tech-trends-*.html"):
        match = REPORT_RE.fullmatch(report.name)
        if not match:
            continue
        try:
            report_date = datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            continue
        reports.append((report_date, report))

    reports.sort(reverse=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    report_links = []
    for report_date, report in reports:
        href = Path("outputs", report.name).as_posix()
        report_links.append(
            f'<li><a href="{html.escape(href)}">'
            f'<time datetime="{report_date:%Y-%m-%d}">{report_date:%Y 年 %m 月 %d 日}</time>'
            '<span>查看日报</span></a></li>'
        )

    if report_links:
        latest_href = Path("outputs", reports[0][1].name).as_posix()
        latest_link = f'<a class="primary" href="{html.escape(latest_href)}">阅读最新一期</a>'
        report_list = "\n".join(report_links)
    else:
        latest_link = ""
        report_list = '<li class="empty">日报尚未生成</li>'

    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="每日科技趋势中文策展报告归档">
  <title>每日技术前沿</title>
  <style>
    *{{box-sizing:border-box}}
    body{{margin:0;background:#f4f6f8;color:#192331;font:15px/1.7 system-ui,-apple-system,"Segoe UI",sans-serif}}
    main{{width:min(760px,calc(100% - 32px));margin:auto;padding:56px 0 80px}}
    header{{padding-bottom:28px;border-bottom:2px solid #174f78}}
    h1{{margin:0;font-size:34px;letter-spacing:0}}
    .lede{{max-width:620px;margin:10px 0 22px;color:#58697c}}
    .primary{{display:inline-block;padding:9px 14px;border-radius:6px;background:#176b99;color:#fff;text-decoration:none;font-weight:700}}
    h2{{margin:34px 0 14px;font-size:20px}}
    ul{{margin:0;padding:0;list-style:none;border-top:1px solid #d8dfe5}}
    li{{border-bottom:1px solid #d8dfe5}}
    li a{{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:16px 4px;color:#174f78;text-decoration:none}}
    li a:hover{{background:#e9f1f5}}
    li span{{color:#637184;font-size:13px}}
    .empty{{padding:18px 4px;color:#637184}}
    footer{{margin-top:30px;color:#637184;font-size:13px}}
    @media(max-width:520px){{main{{padding-top:34px}}h1{{font-size:28px}}li a{{align-items:flex-start;flex-direction:column;gap:2px}}}}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>每日技术前沿</h1>
      <p class="lede">每天阅读过去 24 小时的原始来源，筛选值得关注的技术动态，并以中文归档。</p>
      {latest_link}
    </header>
    <section aria-labelledby="archive-title">
      <h2 id="archive-title">历史日报</h2>
      <ul>
        {report_list}
      </ul>
    </section>
    <footer>内容由 Codex 基于公开来源整理，成熟度与风险说明请以每期正文为准。</footer>
  </main>
</body>
</html>
"""
    output.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=Path(__file__).parent)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent.parent / "index.html")
    args = parser.parse_args()
    build_index(args.reports_dir, args.output)


if __name__ == "__main__":
    main()
