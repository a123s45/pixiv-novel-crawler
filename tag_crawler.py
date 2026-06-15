import time

from auth import PixivAuth
from pixiv_api import PixivAPI
from models import PixivNovel, PendingItem
from index_manager import IndexManager
from downloader import Downloader
from series_judge import SeriesJudge


class TagCrawler:
    def __init__(self, api: PixivAPI, index: IndexManager, downloader: Downloader, judge: SeriesJudge, config: dict):
        self.api = api
        self.index = index
        self.downloader = downloader
        self.judge = judge
        self.config = config
        ts = config.get("tag_search", {})
        self.positive_tags = ts.get("positive_tags", [])
        self.negative_tags = ts.get("negative_tags", [])
        self.reverse_tags = config.get("reverse_tags", [])
        self.min_bookmarks = ts.get("min_bookmarks", 0)
        self.min_words = ts.get("min_words", 0)
        self.max_words = ts.get("max_words", 0)
        self.max_results = ts.get("max_results", 200)

    def run(self):
        if not self.positive_tags:
            print("Tag 检索: 未配置 positive_tags，跳过")
            return

        print(f"\n开始 Tag 检索: {', '.join(self.positive_tags)}")
        total_downloaded = 0

        for tag in self.positive_tags:
            total_downloaded += self._crawl_tag(tag)

        print(f"\nTag 检索完成，共下载 {total_downloaded} 篇")

    def _crawl_tag(self, tag: str) -> int:
        downloaded = 0
        page = 1
        progress = self.index.get_tag_progress(tag)
        start_page = progress.get("last_page", 0) + 1
        page = start_page if start_page > 1 else 1

        while True:
            if self.max_results > 0 and downloaded >= self.max_results:
                print(f"  Tag '{tag}': 达到上限 {self.max_results}，停止")
                break

            novels = self.api.search_novels(tag, page=page, sort=self.config["tag_search"].get("sort", "date_desc"))
            if not novels:
                print(f"  Tag '{tag}': 第 {page} 页无结果，检索完毕")
                break

            for novel in novels:
                if self.max_results > 0 and downloaded >= self.max_results:
                    break
                if self.index.is_downloaded(novel.id):
                    continue
                if not self._passes_filters(novel):
                    continue

                self._process_novel(novel)
                downloaded += 1

            self.index.update_tag_progress(tag, page, novels[-1].id, downloaded)
            page += 1
            time.sleep(0.5)

        return downloaded

    def _passes_filters(self, novel: PixivNovel) -> bool:
        if self.negative_tags:
            if any(nt in novel.tags for nt in self.negative_tags):
                return False
        if self.min_bookmarks > 0 and novel.bookmark_count < self.min_bookmarks:
            return False
        if self.min_words > 0 and novel.word_count < self.min_words:
            return False
        if self.max_words > 0 and novel.word_count > self.max_words:
            return False
        return True

    def _process_novel(self, novel: PixivNovel):
        if self.reverse_tags and any(rt in novel.tags for rt in self.reverse_tags):
            self.index.add_pending(PendingItem(
                novel_id=novel.id,
                title=novel.title,
                matched_tags=[rt for rt in self.reverse_tags if rt in novel.tags],
                url=novel.url,
                source="tag_search",
            ))
            print(f"  [待处理] {novel.title} (反向Tag: {novel.tags})")
            return

        self._download_with_series_check(novel)

    def _download_with_series_check(self, novel: PixivNovel):
        decision, chapter_ids, series_info = self.judge.judge(novel)
        if decision == "merge":
            path = self.downloader.download_series(novel, series_info, chapter_ids)
            print(f"  [系列合并] {series_info.title} → {path}")
        else:
            path = self.downloader.download(novel)
            if path:
                print(f"  [下载] {novel.title} → {path}")
