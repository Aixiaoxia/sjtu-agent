"""sjtu_agent/news_aggregator/sources/jwc.py — 教务处通知公告爬虫。

入口：https://jwc.sjtu.edu.cn/xwtg/tztg.htm
无需登录，直接 HTTP 请求。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from sjtu_agent.news_aggregator.sources.base import BaseNewsSource, NewsItem, CST

_BASE = "https://jwc.sjtu.edu.cn"
_LIST_URL = "https://jwc.sjtu.edu.cn/xwtg/tztg.htm"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def _parse_date(text: str) -> Optional[datetime]:
    """解析教务处日期格式，如 '2026-05-08' 或 '2026/05/08'。"""
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(hour=8, tzinfo=CST)  # 教务处公告默认早上发布
        except ValueError:
            continue
    return None


def _fetch_summary(url: str, timeout: int = 8) -> str:
    """抓取公告详情页，提取正文前 200 字。"""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=timeout)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        # 教务处详情页正文通常在 .v_news_content 或 .article 里
        for sel in [".v_news_content", ".article", "#vsb_content", "article", ".content"]:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(separator=" ", strip=True)
                return text[:200].strip()
        # fallback：取 body 文字
        body = soup.find("body")
        if body:
            return body.get_text(separator=" ", strip=True)[:200]
    except Exception:
        pass
    return ""


class JwcSource(BaseNewsSource):
    """教务处通知公告。"""
    name = "jwc"

    def _fetch(self, hours: int) -> list[NewsItem]:
        r = requests.get(_LIST_URL, headers=_HEADERS, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        items: list[NewsItem] = []
        # 教务处列表页结构：<ul class="news_list"> <li> <a> + <span class="date">
        for li in soup.select("ul.news_list li, .list_item li, li.list-item"):
            a_tag = li.find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            href  = a_tag.get("href", "")
            if not href or not title:
                continue
            # 补全 URL
            if href.startswith("http"):
                url = href
            elif href.startswith("/"):
                url = _BASE + href
            else:
                url = _BASE + "/xwtg/" + href

            # 日期
            date_el = li.find("span") or li.find(class_=re.compile(r"date|time"))
            pub_dt = None
            if date_el:
                pub_dt = _parse_date(date_el.get_text(strip=True))
            if pub_dt is None:
                # 没有日期就假设是今天
                from datetime import datetime as _dt
                pub_dt = _dt.now(CST).replace(hour=8, minute=0, second=0, microsecond=0)

            # 时间过滤
            item_tmp = NewsItem(
                id=self._make_id(url),
                source=self.name,
                title=title,
                summary="",
                url=url,
                published_at=pub_dt,
                category="教务通知",
                tags=["教务处", "通知"],
            )
            if item_tmp.age_hours() > hours:
                continue

            # 抓摘要（并发时由 aggregator 控制，这里串行）
            summary = _fetch_summary(url)
            item_tmp.summary = summary or title
            items.append(item_tmp)

        return items
