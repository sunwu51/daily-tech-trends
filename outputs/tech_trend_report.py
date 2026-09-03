#!/usr/bin/env python3
"""Build a daily, evidence-backed technology trend report.

No third-party packages are required. Optionally set GITHUB_TOKEN to increase
the GitHub API rate limit. Run this file once, or install the supplied Windows
scheduled-task script for a daily 08:00 report.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import datetime as dt
import email.utils
import html
import json
import math
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


UTC = dt.timezone.utc
NOW = dt.datetime.now(UTC)
WINDOW_START = NOW - dt.timedelta(hours=24)
USER_AGENT = "daily-tech-trend-report/1.0 (personal research tool)"
# The final report is authored by the Codex curation pass.  Keep the collector
# preview separate so a manual collection run cannot replace that work.
DEFAULT_OUTPUT = Path(__file__).with_name("tech-trends-raw.html")
DEFAULT_CANDIDATES = Path(__file__).with_name("tech-trend-candidates.json")

RSS_FEEDS = {
    "Cloudflare Blog": "https://blog.cloudflare.com/rss/",
    "Google Developers": "https://developers.googleblog.com/feeds/posts/default",
    "AWS News": "https://aws.amazon.com/about-aws/whats-new/recent/feed/",
    "Kubernetes Blog": "https://kubernetes.io/feed.xml",
    "Rust Blog": "https://blog.rust-lang.org/feed.xml",
}

STOP_WORDS = frozenset(
    "the a an and or for with from into your our how why what new introducing "
    "release released update updates on in of to is are at by as via about".split()
)
TECHNICAL_TITLE_TERMS = frozenset(
    "ai api analytics application architecture browser chip cloud code coding compiler computer "
    "cryptography database data developer devops docker filesystem framework gpu hardware "
    "kernel kubernetes linux macos network open-source operating performance programming "
    "protocol python robotics security server software storage system terminal tool web".split()
)


@dataclass
class Item:
    source: str
    title: str
    url: str
    published: dt.datetime
    summary: str = ""
    engagement: float = 0
    kind: str = "article"
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0
    reasons: list[str] = field(default_factory=list)


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")


def parse_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        normalized = value.strip().replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(normalized)
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def is_within_window(value: dt.datetime) -> bool:
    return WINDOW_START <= value < NOW


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def is_technical_title(title: str) -> bool:
    words = set(re.findall(r"[a-z][a-z0-9+#.-]*", title.lower()))
    return bool(words & TECHNICAL_TITLE_TERMS) or title.lower().startswith("show hn:")


def github_trending_items() -> list[Item]:
    """Collect the first ten repositories from both current GitHub Daily views."""
    found: dict[str, Item] = {}
    views = (
        ("GitHub Trending Daily", "https://github.com/trending?since=daily"),
        ("GitHub Trending Daily (Chinese)", "https://github.com/trending?since=daily&spoken_language_code=zh"),
    )
    for source, url in views:
        try:
            document = fetch_text(url)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            print(f"GitHub skipped: {exc}", file=sys.stderr)
            continue
        articles = re.findall(r'<article class="Box-row">(.*?)</article>', document, re.DOTALL)
        for article in articles[:10]:
            repository = re.search(r'<h2[^>]*>.*?href="/([^"/]+/[^"/]+)"[^>]*>(.*?)</a>', article, re.DOTALL)
            if not repository:
                continue
            name = clean_text(repository.group(2)).replace(" / ", "/")
            if not name or name in found:
                continue
            description = re.search(r'<p class="col-9[^>]*>(.*?)</p>', article, re.DOTALL)
            language = re.search(r'itemprop="programmingLanguage">(.*?)</span>', article, re.DOTALL)
            today = re.search(r'([\d,]+)\s+stars today', article)
            today_stars = int(today.group(1).replace(",", "")) if today else 0
            found[name] = Item(
                source=source,
                title=name,
                url=f"https://github.com/{repository.group(1)}",
                published=NOW,
                summary=clean_text(description.group(1)) if description else "No repository description provided.",
                engagement=float(today_stars),
                kind="project_trending",
                metadata={
                    "language": clean_text(language.group(1)) if language else "Unspecified",
                    "stars_today": today_stars,
                    "trending_view": source,
                },
            )
    return list(found.values())


def hacker_news_items() -> list[Item]:
    try:
        ids = fetch_json("https://hacker-news.firebaseio.com/v0/newstories.json")[:100]
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"Hacker News skipped: {exc}", file=sys.stderr)
        return []
    def get_story(story_id: int) -> dict[str, Any] | None:
        try:
            return fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            return None

    # HN's API requires one request per item. A small pool keeps the report
    # responsive without placing high load on the public endpoint.
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        stories = list(executor.map(get_story, ids))
    items: list[Item] = []
    for story_id, story in zip(ids, stories):
        if not story or story.get("type") != "story":
            continue
        if not is_technical_title(story.get("title", "")):
            continue
        published = dt.datetime.fromtimestamp(story.get("time", 0), UTC)
        if not is_within_window(published):
            continue
        points, comments = story.get("score", 0), story.get("descendants", 0)
        items.append(Item(
            source="Hacker News", title=story.get("title", "Untitled"),
            url=story.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
            published=published, summary=f"{points} points and {comments} comments on Hacker News.",
            engagement=float(points + comments * 2), kind="discussion",
            metadata={"points": points, "comments": comments, "hn_url": f"https://news.ycombinator.com/item?id={story_id}"},
        ))
    return items


def rss_items() -> list[Item]:
    items: list[Item] = []
    for source, feed_url in RSS_FEEDS.items():
        try:
            root = ET.fromstring(fetch_text(feed_url))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ET.ParseError) as exc:
            print(f"{source} skipped: {exc}", file=sys.stderr)
            continue
        for node in root.findall(".//item"):
            published = parse_date(node.findtext("pubDate"))
            if not published or not is_within_window(published):
                continue
            items.append(Item(source, clean_text(node.findtext("title") or "Untitled"),
                node.findtext("link") or feed_url, published,
                clean_text(node.findtext("description") or ""), kind="official"))
        ns = "{http://www.w3.org/2005/Atom}"
        for node in root.findall(f".//{ns}entry"):
            published = parse_date(node.findtext(f"{ns}published") or node.findtext(f"{ns}updated"))
            if not published or not is_within_window(published):
                continue
            link = next((x.attrib.get("href") for x in node.findall(f"{ns}link") if x.attrib.get("href")), feed_url)
            summary = node.findtext(f"{ns}summary") or node.findtext(f"{ns}content") or ""
            items.append(Item(source, clean_text(node.findtext(f"{ns}title") or "Untitled"), link,
                published, clean_text(summary), kind="official"))
    return items


def terms(item: Item) -> set[str]:
    text = f"{item.title} {item.summary} {' '.join(item.metadata.get('topics', []))}".lower()
    return {word for word in re.findall(r"[a-z][a-z0-9+.#-]{2,}", text) if word not in STOP_WORDS}


def score_and_cluster(items: list[Item]) -> list[Item]:
    # A source-normalized logarithmic score prevents HN point counts from
    # overwhelming early GitHub projects or zero-engagement official releases.
    by_source: dict[str, list[float]] = collections.defaultdict(list)
    for item in items:
        by_source[item.source].append(math.log1p(item.engagement))
    max_by_source = {source: max(values, default=1) for source, values in by_source.items()}
    all_terms = [(item, terms(item)) for item in items]
    for item, item_terms in all_terms:
        engagement = math.log1p(item.engagement) / max(1, max_by_source[item.source])
        age_hours = max(0, (NOW - item.published).total_seconds() / 3600)
        freshness = max(0, 1 - age_hours / 30)
        independent_sources = {other.source for other, other_terms in all_terms
                               if other is not item and len(item_terms & other_terms) >= 2}
        corroboration = min(1, len(independent_sources) / 2)
        official = 1 if item.kind == "official" else 0
        research = 0.45 if item.kind == "research" else 0
        item.score = round(100 * (0.43 * engagement + 0.22 * freshness + 0.23 * corroboration + 0.12 * max(official, research)))
        if item.engagement:
            item.reasons.append(f"{item.source} engagement: {int(item.engagement)}")
        if independent_sources:
            item.reasons.append("cross-source signal: " + ", ".join(sorted(independent_sources)))
        if official:
            item.reasons.append("official engineering release or announcement")
        if item.kind == "project_trending":
            item.reasons.append(f"GitHub Trending Daily: {item.metadata['stars_today']} stars today; {item.metadata['language']}")
    return sorted(items, key=lambda item: (item.score, item.published), reverse=True)


def short(value: str, limit: int = 300) -> str:
    value = clean_text(value)
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "..."


def render(items: list[Item], output: Path, failures: list[str]) -> None:
    grouped: dict[str, list[Item]] = collections.OrderedDict()
    names = {"project_trending": "GitHub Trending Daily projects",
             "discussion": "Engineering discussions",
             "research": "Research and methods", "official": "Official releases and infrastructure"}
    for item in items:
        grouped.setdefault(names[item.kind], []).append(item)
    parts = []
    for group, group_items in grouped.items():
        cards = []
        for item in group_items[:12]:
            metadata = ""
            if item.kind == "project_trending":
                metadata = (f"<span>{html.escape(item.metadata['language'])}</span>"
                            f"<span>{item.metadata['stars_today']} stars today</span>")
            elif item.kind == "research":
                metadata = "".join(f"<span>{html.escape(cat)}</span>" for cat in item.metadata.get("categories", [])[:4])
            evidence = "<br>".join(html.escape(reason) for reason in item.reasons) or "Recent publication within the report window."
            cards.append(f'''<article class="card"><div class="top"><span class="source">{html.escape(item.source)}</span><strong>{item.score}</strong></div>
              <h3><a href="{html.escape(item.url, quote=True)}">{html.escape(item.title)}</a></h3>
              <p>{html.escape(short(item.summary))}</p><div class="meta">{metadata}</div>
              <div class="evidence"><b>Why it matters</b><br>{evidence}</div></article>''')
        parts.append(f"<section><h2>{group}</h2><div class='grid'>{''.join(cards)}</div></section>")
    failed = f"<p class='notice'>Unavailable sources: {html.escape(', '.join(failures))}</p>" if failures else ""
    generated = NOW.astimezone().strftime("%Y-%m-%d %H:%M %Z")
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daily Technology Trends</title><style>
*{{box-sizing:border-box}} body{{margin:0;background:#f6f7f9;color:#18212f;font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}} main{{max-width:1280px;margin:auto;padding:34px 24px 70px}} header{{border-bottom:1px solid #d8dce3;padding-bottom:20px}} h1{{font-size:30px;margin:0}} header p{{margin:8px 0 0;color:#586274}} h2{{font-size:20px;margin:38px 0 14px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}} .card{{background:white;border:1px solid #dfe3e8;border-radius:7px;padding:17px;display:flex;flex-direction:column;gap:10px}} .top{{display:flex;justify-content:space-between;align-items:center}} .top strong{{background:#152f4f;color:white;padding:2px 9px;border-radius:999px}} .source{{font-size:12px;color:#48647e;font-weight:700;text-transform:uppercase}} h3{{font-size:17px;line-height:1.3;margin:0}} a{{color:#0b5cab;text-decoration:none}} a:hover{{text-decoration:underline}} p{{margin:0;color:#445163}} .meta{{display:flex;gap:6px;flex-wrap:wrap}} .meta span{{font-size:12px;background:#edf2f6;color:#42566d;padding:2px 7px;border-radius:3px}} .evidence{{border-top:1px solid #e7e9ed;padding-top:10px;font-size:13px;color:#576273}} .notice{{background:#fff4d8;padding:9px 12px;border-left:3px solid #d49100}} footer{{margin-top:36px;color:#6c7481;font-size:13px}} @media(max-width:560px){{main{{padding:24px 14px}}h1{{font-size:25px}}}}</style></head>
<body><main><header><h1>Daily Technology Trends</h1><p>Past 24 hours, generated {html.escape(generated)}. Scores combine source-normalized engagement, freshness, cross-source evidence, and primary-source weight.</p></header>{failed}{''.join(parts)}<footer>Data: GitHub Search API, Hacker News API, and selected official RSS feeds. A score ranks attention signals, not technical correctness or production readiness.</footer></main></body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")


def write_candidates(items: list[Item], output: Path, failures: list[str]) -> None:
    """Write bounded, source-attributed input for the Codex curation pass."""
    data = {
        "generated_at": NOW.isoformat(),
        "window_start": WINDOW_START.isoformat(),
        "unavailable_sources": failures,
        "instructions": "Use primary URLs to verify claims before producing Chinese summaries. Treat scores as selection signals, not conclusions.",
        "items": [{
            "source": item.source, "type": item.kind, "title": item.title, "url": item.url,
            "published_at": item.published.isoformat(), "raw_summary": short(item.summary, 700),
            "score": item.score, "reasons": item.reasons, "metadata": item.metadata,
        } for item in items[:45]],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect candidates for the daily technology trend report.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates-output", type=Path, default=DEFAULT_CANDIDATES,
                        help="Structured source data for the Codex Chinese curation pass.")
    parser.add_argument("--window-end", type=str,
                        help="ISO 8601 timestamp for the exclusive end of the 24-hour collection window.")
    parser.add_argument("--include-github-trending", action="store_true",
                        help="Include the current GitHub Trending Daily and Chinese views.")
    args = parser.parse_args()
    if args.window_end:
        window_end = parse_date(args.window_end)
        if not window_end:
            parser.error("--window-end must be an ISO 8601 timestamp with a timezone, such as 2026-09-03T07:00:00+08:00")
        global NOW, WINDOW_START
        NOW = window_end
        WINDOW_START = NOW - dt.timedelta(hours=24)
    collectors = [("Hacker News", hacker_news_items), ("RSS feeds", rss_items)]
    if args.include_github_trending:
        collectors.insert(0, ("GitHub Trending", github_trending_items))
    collected: list[Item] = []
    failures: list[str] = []
    for name, collector in collectors:
        try:
            results = collector()
            collected.extend(results)
            if not results:
                failures.append(name)
        except Exception as exc:  # Report generation should survive a source outage.
            print(f"{name} failed: {exc}", file=sys.stderr)
            failures.append(name)
    candidates = score_and_cluster(collected)
    write_candidates(candidates, args.candidates_output.resolve(), failures)
    render(candidates, args.output.resolve(), failures)
    print(f"Wrote collector preview {args.output.resolve()} and {args.candidates_output.resolve()} with {len(candidates)} candidates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
