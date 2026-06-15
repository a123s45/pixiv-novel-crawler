import os
import re

from pixiv_api import PixivAPI
from models import PixivNovel
from index_manager import IndexManager


class Downloader:
    def __init__(self, api: PixivAPI, index: IndexManager, config: dict):
        self.api = api
        self.index = index
        self.output_dir = config["download"]["output_dir"]
        self.evaluator = None
        self.translator = None
        self.archiver = None
        os.makedirs(self.output_dir, exist_ok=True)

    def set_post_processors(self, evaluator, translator, archiver):
        self.evaluator = evaluator
        self.translator = translator
        self.archiver = archiver

    def _after_download(self, novel: PixivNovel, filepath: str):
        if not self.evaluator or not self.archiver:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                full_text = f.read()

            result = self.evaluator.evaluate(novel, full_text)

            if result.rejected:
                self.archiver.archive_failed(novel, result)
                return

            if self.translator:
                orig_path, trans_path = self.translator.process(novel, full_text)
                self.archiver.archive_qualified(novel, result, orig_path, trans_path)
            else:
                self.archiver.archive_qualified(novel, result, original_path=filepath)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def download(self, novel: PixivNovel) -> str:
        if self.index.is_downloaded(novel.id):
            return ""

        safe_title = self._sanitize_filename(novel.title)
        filename = f"{safe_title}_{novel.id}.txt"
        filepath = os.path.join(self.output_dir, filename)

        text = self.api.get_novel_text(novel.id)

        content = f"{novel.title}\n{'=' * 40}\n\n{text}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        self.index.mark_downloaded(novel.id)
        self._after_download(novel, filepath)
        return filepath

    def download_series(self, novel: PixivNovel, series_info, chapter_ids: list[str]) -> str:
        safe_title = self._sanitize_filename(series_info.title or novel.title)
        filename = f"{safe_title}_{series_info.id}.txt"
        filepath = os.path.join(self.output_dir, filename)

        lines = [f"{series_info.title}", "=" * 40, ""]
        if series_info.caption:
            lines.extend([series_info.caption, "", "-" * 40, ""])

        for cid in chapter_ids:
            text = self.api.get_novel_text(cid)
            chapter_info = next((c for c in series_info.chapters if c.id == cid), None)
            if chapter_info:
                lines.append(f"【{chapter_info.title}】")
                lines.append("")
            lines.append(text)
            lines.append("")

        content = "\n".join(lines)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        for cid in chapter_ids:
            self.index.mark_downloaded(cid)
        return filepath

    def _sanitize_filename(self, name: str) -> str:
        name = re.sub(r'[\\/:*?"<>|]', "_", name)
        return name[:120].strip()
