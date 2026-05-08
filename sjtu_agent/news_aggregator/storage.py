"""sjtu_agent/news_aggregator/storage.py — 已推送去重 + 历史归档。"""
from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from sjtu_agent import paths as _paths
from sjtu_agent.paths import atomic_write_json, read_json_safe

if TYPE_CHECKING:
    from sjtu_agent.news_aggregator.sources.base import NewsItem

CST = timezone(timedelta(hours=8))
_TTL_DAYS = 7  # 历史记录保留天数


class NewsStorage:
    """管理已推送新闻 ID，防止重复推送。"""

    def __init__(self):
        self._path = _paths.NEWS_HISTORY_PATH

    def _load(self) -> dict:
        return read_json_safe(self._path, default={"pushed": {}, "updated_at": ""})

    def _save(self, data: dict) -> None:
        data["updated_at"] = datetime.now(CST).isoformat()
        atomic_write_json(self._path, data)

    def dedupe(self, items: list["NewsItem"]) -> list["NewsItem"]:
        """过滤掉已推送过的新闻。"""
        data = self._load()
        pushed = data.get("pushed", {})
        return [item for item in items if item.id not in pushed]

    def mark_pushed(self, news_ids: list[str]) -> None:
        """标记这批新闻已推送。"""
        data = self._load()
        pushed = data.get("pushed", {})
        now_ts = time.time()
        for nid in news_ids:
            pushed[nid] = now_ts
        # 清理 7 天前的记录
        cutoff = now_ts - _TTL_DAYS * 86400
        pushed = {k: v for k, v in pushed.items() if v > cutoff}
        data["pushed"] = pushed
        self._save(data)

    def get_pushed_count(self) -> int:
        data = self._load()
        return len(data.get("pushed", {}))
