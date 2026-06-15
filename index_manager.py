import json
import os
from datetime import datetime, timedelta
from typing import Optional

from models import ScannedRecord, PendingItem, SeriesJudgment


class IndexManager:
    def __init__(self, path: str = "./index.json"):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "ranking_scanned": [],
            "tag_crawl_progress": {},
            "downloaded_ids": [],
            "pending_list": [],
            "series_judgments": {},
        }

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_ranking_period_scanned(self, period_key: str) -> bool:
        return any(r["period_key"] == period_key for r in self.data["ranking_scanned"])

    def add_ranking_record(self, record: ScannedRecord):
        self.data["ranking_scanned"].append({
            "period_key": record.period_key,
            "scan_type": record.scan_type,
            "scanned_at": record.scanned_at,
            "novel_ids": record.novel_ids,
            "downloaded": record.downloaded,
            "pending_ids": record.pending_ids,
        })
        self.save()

    def get_tag_progress(self, tag: str) -> dict:
        return self.data["tag_crawl_progress"].get(tag, {"last_page": 0, "last_novel_id": None, "total_downloaded": 0})

    def update_tag_progress(self, tag: str, page: int, last_novel_id: str, downloaded: int):
        self.data["tag_crawl_progress"][tag] = {
            "last_page": page,
            "last_novel_id": last_novel_id,
            "total_downloaded": downloaded,
        }
        self.save()

    def is_downloaded(self, novel_id: str) -> bool:
        return novel_id in self.data["downloaded_ids"]

    def mark_downloaded(self, novel_id: str):
        if novel_id not in self.data["downloaded_ids"]:
            self.data["downloaded_ids"].append(novel_id)
            self.save()

    def get_pending_list(self) -> list[PendingItem]:
        return [PendingItem(**p) for p in self.data["pending_list"]]

    def add_pending(self, item: PendingItem):
        ids = [p["novel_id"] for p in self.data["pending_list"]]
        if item.novel_id not in ids:
            self.data["pending_list"].append({
                "novel_id": item.novel_id,
                "title": item.title,
                "matched_tags": item.matched_tags,
                "url": item.url,
                "source": item.source,
            })
            self.save()

    def remove_pending(self, novel_id: str):
        self.data["pending_list"] = [p for p in self.data["pending_list"] if p["novel_id"] != novel_id]
        self.save()

    def get_series_judgment(self, series_id: str) -> Optional[str]:
        return self.data["series_judgments"].get(series_id)

    def save_series_judgment(self, judgment: SeriesJudgment):
        self.data["series_judgments"][judgment.series_id] = {
            "decision": judgment.decision,
            "reason": judgment.reason,
        }
        self.save()

    @staticmethod
    def get_ranking_periods(weeks_back: int = 52) -> list[str]:
        today = datetime.now()
        periods = []
        for i in range(weeks_back):
            monday = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
            sunday = monday + timedelta(days=6)
            periods.append(f"{monday.strftime('%Y-%m-%d')}~{sunday.strftime('%Y-%m-%d')}")
        return periods
