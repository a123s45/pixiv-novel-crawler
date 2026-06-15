import json
import os
import shutil
from datetime import datetime

from models import PixivNovel, QualityResult, ArchiveRecord


class Archiver:
    def __init__(self, config: dict):
        self.archive_dir = config.get("archive", {}).get("output_dir", "./archive")
        self.index_path = os.path.join(self.archive_dir, "index.json")
        os.makedirs(os.path.join(self.archive_dir, "qualified", "中文"), exist_ok=True)
        os.makedirs(os.path.join(self.archive_dir, "qualified", "翻译"), exist_ok=True)
        self._load_index()

    def _load_index(self):
        if os.path.exists(self.index_path):
            with open(self.index_path, "r", encoding="utf-8") as f:
                self.index = json.load(f)
        else:
            self.index = {"qualified": [], "failed": []}

    def _save_index(self):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def archive_qualified(self, novel: PixivNovel, result: QualityResult,
                          original_path="", translated_path=""):
        translated = bool(translated_path and os.path.exists(translated_path))
        target_dir = "翻译" if translated else "中文"
        lang = novel.language

        dest_orig = ""
        dest_trans = ""

        base = f"{self._safe_name(novel.title)}_{novel.id}"

        if original_path and os.path.exists(original_path):
            dest_orig = os.path.join(self.archive_dir, "qualified", target_dir, f"{base}_original.txt")
            shutil.move(original_path, dest_orig)
        if translated and translated_path and os.path.exists(translated_path):
            dest_trans = os.path.join(self.archive_dir, "qualified", target_dir, f"{base}.txt")
            shutil.move(translated_path, dest_trans)

        record = {
            "novel_id": novel.id,
            "title": novel.title,
            "lang": lang,
            "translated": translated,
            "original_file": dest_orig,
            "translated_file": dest_trans,
            "word_count": novel.word_count,
            "bookmarks": novel.bookmark_count,
            "tags": novel.tags,
            "quality_score": result.quality_score,
            "ai_summary": result.summary,
            "has_advertisement": result.has_advertisement,
            "requires_payment": result.requires_payment,
            "archived_at": datetime.now().isoformat(),
        }

        self.index["qualified"].append(record)
        self._save_index()

    def archive_failed(self, novel: PixivNovel, result: QualityResult):
        entry = {
            "novel_id": novel.id,
            "title": novel.title,
            "bookmarks": novel.bookmark_count,
            "tags": novel.tags,
            "word_count": novel.word_count,
            "reasons": result.reasons,
            "tag_fraud": result.tag_fraud,
            "fraud_tags": result.fraud_tags,
            "quality_score": result.quality_score,
            "summary": result.summary,
            "evaluated_at": datetime.now().isoformat(),
        }
        self.index["failed"].append(entry)
        self._save_index()

    def get_qualified(self, search="", tag_filter=None):
        items = self.index.get("qualified", [])
        if search:
            s = search.lower()
            items = [i for i in items if s in i.get("title", "").lower()
                     or any(s in t.lower() for t in i.get("tags", []))]
        return list(reversed(items))

    def get_failed(self):
        return list(reversed(self.index.get("failed", [])))

    def get_summary(self):
        q = self.index.get("qualified", [])
        f = self.index.get("failed", [])
        scores = [i.get("quality_score", 0) for i in q if i.get("quality_score")]
        return {
            "qualified_count": len(q),
            "failed_count": len(f),
            "total_words": sum(i.get("word_count", 0) for i in q),
            "translated_count": sum(1 for i in q if i.get("translated")),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        }

    def _safe_name(self, name: str) -> str:
        import re
        return re.sub(r'[\\/:*?"<>|]', "_", name)[:80]
