"""sjtu_agent/news_aggregator/sources/canvas.py — Canvas 课程通告爬虫。

使用 Canvas API，需要 canvas_token。
只抓通告（announcement），不抓作业（已有 ddl_checker）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import requests

from sjtu_agent.news_aggregator.sources.base import BaseNewsSource, NewsItem, CST
from sjtu_agent import paths as _paths
from sjtu_agent.paths import read_json_safe


def _parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(CST)
    except Exception:
        return None


class CanvasSource(BaseNewsSource):
    """Canvas 课程通告。"""
    name = "canvas"

    def _fetch(self, hours: int) -> list[NewsItem]:
        cfg = read_json_safe(_paths.CONFIG_PATH, default={})
        token = cfg.get("canvas_token", "")
        base_url = cfg.get("canvas_base_url", "https://oc.sjtu.edu.cn")
        if not token or token.startswith("YOUR_"):
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        # 获取用户所有课程
        try:
            r = requests.get(
                f"{base_url}/api/v1/courses",
                params={"enrollment_state": "active", "per_page": 50},
                headers=headers,
                timeout=15,
            )
            courses = r.json() if r.ok else []
            if not isinstance(courses, list):
                courses = []
        except Exception:
            return []

        context_codes = [f"course_{c['id']}" for c in courses if isinstance(c, dict) and "id" in c]
        if not context_codes:
            return []

        # 获取通告
        items: list[NewsItem] = []
        try:
            r = requests.get(
                f"{base_url}/api/v1/announcements",
                params={
                    "context_codes[]": context_codes,
                    "per_page": 30,
                    "start_date": "",
                },
                headers=headers,
                timeout=15,
            )
            announcements = r.json() if r.ok else []
            if not isinstance(announcements, list):
                announcements = []
        except Exception:
            return []

        # 课程 ID → 名称映射
        course_map = {str(c["id"]): c.get("name", "") for c in courses if isinstance(c, dict)}

        for ann in announcements:
            title = ann.get("title", "").strip()
            url   = ann.get("html_url", "")
            if not title or not url:
                continue

            pub_dt = _parse_iso(ann.get("posted_at") or ann.get("created_at", ""))
            if pub_dt is None:
                continue

            # 课程名
            ctx_code = ann.get("context_code", "")
            course_id = ctx_code.replace("course_", "")
            course_name = course_map.get(course_id, "")
            author = f"{course_name} · {ann.get('author', {}).get('display_name', '')}"

            # 摘要：去除 HTML 标签
            import re
            body = re.sub(r"<[^>]+>", " ", ann.get("message", ""))
            body = re.sub(r"\s+", " ", body).strip()

            item = NewsItem(
                id=self._make_id(url),
                source=self.name,
                title=title,
                summary=self._truncate(body or title),
                url=url,
                published_at=pub_dt,
                author=author.strip(" ·"),
                category="Canvas 通告",
                tags=["Canvas", "课程通告"],
            )
            if item.age_hours() <= hours:
                items.append(item)

        return items
