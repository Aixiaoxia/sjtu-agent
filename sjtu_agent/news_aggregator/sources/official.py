"""sjtu_agent/news_aggregator/sources/official.py — 交大官网新闻爬虫。

入口：https://news.sjtu.edu.cn/
优先尝试 RSS，失败降级到 HTML 解析。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import requests

from sjtu_agent.news_aggregator.sources.base import BaseNewsSource, NewsItem, CST

_BASE = "https://news.sjtu.edu.cn"
_RSS_URL = "https://news.sjtu.edu.cn/rss.xml"
_NEWS_URL = "https://news.sjtu.edu.cn/jdyw/index.html"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/rss+xml"}


def _parse_rss_date(s: str) -> Optional[datetime]:
    """解析 RSS 日期格式（RFC 2822）。"""
    if not s:
        return None
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        return dt.astimezone(CST)
    except Exception:
        pass
    # fallback: ISO
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(CST)
    except Exception:
        return None


class OfficialSource(BaseNewsSource):
    """交大官网新闻。"""
    name = "official"

    def _fetch(self, hours: int) -> list[NewsItem]:
        # 优先 RSS
        items = self._fetch_rss(hours)
        if items:
            return items
        # 降级 HTML
        return self._fetch_html(hours)

    def _fetch_rss(self, hours: int) -> list[NewsItem]:
        try:
            import feedparser
        except ImportError:
            return []
        try:
            feed = feedparser.parse(_RSS_URL)
            items = []
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                url   = entry.get("link", "")
                if not title or not url:
                    continue
                pub_dt = _parse_rss_date(entry.get("published", ""))
                if pub_dt is None:
                    continue
                item = NewsItem(
                    id=self._make_id(url),
                    source=self.name,
                    title=title,
                    summary=self._truncate(entry.get("summary", "") or title),
                    url=url,
                    published_at=pub_dt,
                    author=entry.get("author", "交大新闻网"),
                    category="交大新闻",
                    tags=["官网", "新闻"],
                )
                if item.age_hours() <= hours:
                    items.append(item)
            return items
        except Exception as e:
            print(f"[news/official] RSS 失败：{e}", flush=True)
            return []

    def _fetch_html(self, hours: int) -> list[NewsItem]:
        try:
            from bs4 import BeautifulSoup
            r = requests.get(_NEWS_URL, headers=_HEADERS, timeout=15)
            r.encoding = r.apparent_encoding or "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            items = []
            for a in soup.select("a[href]"):
                title = a.get_text(strip=True)
                href  = a.get("href", "")
                if not title or len(title) < 5 or not href:
                    continue
                url = href if href.startswith("http") else _BASE + href
                # 没有日期信息，假设是今天
                from datetime import datetime as _dt
                pub_dt = _dt.now(CST).replace(hour=8, minute=0, second=0, microsecond=0)
                item = NewsItem(
                    id=self._make_id(url),
                    source=self.name,
                    title=title,
                    summary=title,
                    url=url,
                    published_at=pub_dt,
                    category="交大新闻",
                    tags=["官网"],
                )
                items.append(item)
            return items[:20]  # 限制数量
        except Exception as e:
            print(f"[news/official] HTML 失败：{e}", flush=True)
            return []
