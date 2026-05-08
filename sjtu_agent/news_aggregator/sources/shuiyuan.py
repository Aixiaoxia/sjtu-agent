"""sjtu_agent/news_aggregator/sources/shuiyuan.py — 水源社区热帖爬虫。

使用 Discourse JSON API，需要 shuiyuan_user_api_key 或 shuiyuan_cookies。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import requests

from sjtu_agent.news_aggregator.sources.base import BaseNewsSource, NewsItem, CST
from sjtu_agent import paths as _paths
from sjtu_agent.paths import read_json_safe

_BASE = "https://shuiyuan.sjtu.edu.cn"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        # Discourse 返回 ISO 8601，如 "2026-05-08T02:00:00.000Z"
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(CST)
    except Exception:
        return None


class ShuiyuanSource(BaseNewsSource):
    """水源社区 24 小时热帖。"""
    name = "shuiyuan"

    def __init__(self, min_views: int = 50, min_likes: int = 3):
        self.min_views = min_views
        self.min_likes = min_likes

    def _get_headers(self) -> dict:
        cfg = read_json_safe(_paths.CONFIG_PATH, default={})
        headers = {"User-Agent": _UA, "Accept": "application/json"}
        api_key = cfg.get("shuiyuan_user_api_key", "")
        client_id = cfg.get("shuiyuan_user_api_client_id", "")
        if api_key and client_id:
            headers["User-Api-Key"] = api_key
            headers["User-Api-Client-Id"] = client_id
            return headers
        # fallback: cookie
        cookies_dict = cfg.get("shuiyuan_cookies", {})
        if cookies_dict:
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies_dict.items())
            headers["Cookie"] = cookie_str
        return headers

    def _fetch(self, hours: int) -> list[NewsItem]:
        headers = self._get_headers()
        items: list[NewsItem] = []

        # 1. 24 小时热帖
        try:
            r = requests.get(
                f"{_BASE}/top.json?period=daily",
                headers=headers,
                timeout=15,
            )
            data = r.json()
            topics = data.get("topic_list", {}).get("topics", [])
        except Exception as e:
            print(f"[news/shuiyuan] top.json 失败：{e}", flush=True)
            topics = []

        # 2. 最新帖子（补充热帖可能遗漏的新内容）
        try:
            r2 = requests.get(
                f"{_BASE}/latest.json?order=created",
                headers=headers,
                timeout=15,
            )
            data2 = r2.json()
            latest = data2.get("topic_list", {}).get("topics", [])
            # 合并，去重
            seen_ids = {t["id"] for t in topics}
            for t in latest:
                if t["id"] not in seen_ids:
                    topics.append(t)
        except Exception:
            pass

        for topic in topics:
            title = topic.get("title", "").strip()
            if not title:
                continue

            topic_id = topic.get("id")
            slug = topic.get("slug", str(topic_id))
            url = f"{_BASE}/t/{slug}/{topic_id}"

            # 时间
            created_at = _parse_iso(topic.get("created_at", ""))
            if created_at is None:
                continue

            item_tmp = NewsItem(
                id=self._make_id(url),
                source=self.name,
                title=title,
                summary="",
                url=url,
                published_at=created_at,
                author=topic.get("last_poster_username", ""),
                category=self._guess_category(topic),
                tags=["水源", "社区"],
            )
            if item_tmp.age_hours() > hours:
                continue

            # 热度过滤（避免推送冷门帖）
            views = topic.get("views", 0)
            likes = topic.get("like_count", 0)
            posts = topic.get("posts_count", 1)
            if views < self.min_views and likes < self.min_likes and posts < 5:
                continue

            # 摘要：用 excerpt 字段（Discourse 自带）
            excerpt = topic.get("excerpt", "")
            if not excerpt:
                excerpt = f"回复 {posts} 条，{views} 次浏览"
            item_tmp.summary = self._truncate(excerpt)
            items.append(item_tmp)

        return items

    def _guess_category(self, topic: dict) -> str:
        cat_id = topic.get("category_id", 0)
        # 水源常见分类 ID（可能随时间变化，仅供参考）
        _CAT_MAP = {
            4: "学习交流", 5: "生活服务", 6: "二手交易",
            7: "校园活动", 8: "求职就业", 9: "娱乐休闲",
        }
        return _CAT_MAP.get(cat_id, "水源社区")
