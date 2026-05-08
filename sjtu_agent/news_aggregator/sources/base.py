"""sjtu_agent/news_aggregator/sources/base.py — 信息源抽象基类与数据结构。"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))


@dataclass
class NewsItem:
    """统一的新闻数据结构。"""
    id: str                          # 全局唯一 ID（source:url_hash）
    source: str                      # 来源标识（jwc / shuiyuan / official / canvas）
    title: str                       # 标题
    summary: str                     # 摘要（200 字以内）
    url: str                         # 原文链接
    published_at: datetime           # 发布时间（必须带 CST 时区）
    author: str = ""                 # 作者/部门
    category: str = ""               # 分类
    tags: list[str] = field(default_factory=list)

    def age_hours(self) -> float:
        """距现在多少小时。"""
        now = datetime.now(CST)
        pub = self.published_at
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=CST)
        return (now - pub).total_seconds() / 3600


class BaseNewsSource(ABC):
    """所有信息源的抽象基类。"""
    name: str = "base"
    enabled: bool = True

    def fetch_recent(self, hours: int = 24) -> list[NewsItem]:
        """获取最近 N 小时的新内容。失败时返回空列表，不抛异常。"""
        if not self.enabled:
            return []
        try:
            return self._fetch(hours)
        except Exception as e:
            print(f"[news/{self.name}] 采集失败：{e}", flush=True)
            return []

    @abstractmethod
    def _fetch(self, hours: int) -> list[NewsItem]:
        """子类实现具体采集逻辑。"""
        ...

    def _make_id(self, url: str) -> str:
        return f"{self.name}:{hashlib.md5(url.encode()).hexdigest()[:12]}"

    def _truncate(self, text: str, max_len: int = 200) -> str:
        text = text.strip()
        return text[:max_len] + "…" if len(text) > max_len else text
