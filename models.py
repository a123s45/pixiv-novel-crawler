from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class PixivNovel:
    id: str
    title: str
    tags: list[str]
    user_id: str
    user_name: str
    bookmark_count: int
    word_count: int
    text_count: int
    create_date: str
    upload_date: str
    description: str
    series_id: Optional[str] = None
    series_title: Optional[str] = None
    language: str = "ja"
    url: str = ""

    @property
    def is_series(self) -> bool:
        return self.series_id is not None


@dataclass
class SeriesInfo:
    id: str
    title: str
    caption: str
    tags: list[str]
    content_count: int
    chapters: list["ChapterInfo"] = field(default_factory=list)


@dataclass
class ChapterInfo:
    id: str
    title: str
    tags: list[str]
    order: int
    description: str = ""


@dataclass
class ScannedRecord:
    period_key: str
    scan_type: str  # "ranking" | "tag"
    scanned_at: str
    novel_ids: list[str]
    downloaded: int = 0
    pending_ids: list[str] = field(default_factory=list)


@dataclass
class PendingItem:
    novel_id: str
    title: str
    matched_tags: list[str]
    url: str
    source: str  # "ranking" or "tag_search"


@dataclass
class SeriesJudgment:
    series_id: str
    decision: str  # "merge" | "individual"
    reason: str = ""

@dataclass
class QualityResult:
    novel_id: str
    title: str
    rejected: bool
    reasons: list[str] = field(default_factory=list)
    is_completed: bool = True
    has_advertisement: bool = False
    requires_payment: bool = False
    tag_fraud: bool = False
    fraud_tags: list[str] = field(default_factory=list)
    quality_score: int = 50
    summary: str = ""
    words_checked: int = 0

@dataclass
class ArchiveRecord:
    novel_id: str
    title: str
    lang: str
    translated: bool
    original_file: str
    translated_file: str
    word_count: int
    bookmarks: int
    tags: list[str] = field(default_factory=list)
    quality_score: int = 50
    ai_summary: str = ""
    style_features: list[str] = field(default_factory=list)
    tag_relevance: dict = field(default_factory=dict)
    has_advertisement: bool = False
    requires_payment: bool = False
    archived_at: str = ""
