from datetime import datetime, timedelta

from auth import PixivAuth
from pixiv_api import PixivAPI
from models import ScannedRecord, PixivNovel, PendingItem
from index_manager import IndexManager
from downloader import Downloader
from series_judge import SeriesJudge
from tag_crawler import TagCrawler


class RankingCrawler:
    def __init__(self, api: PixivAPI, index: IndexManager, downloader: Downloader, judge: SeriesJudge, tag_crawler: TagCrawler, config: dict):
        self.api = api
        self.index = index
        self.downloader = downloader
        self.judge = judge
        self.tag_crawler = tag_crawler
        self.config = config
        rc = config.get("ranking", {})
        self.mode = rc.get("mode", "weekly_r18")
        self.top_n = rc.get("top_n", 100)
        self.bookmark_threshold = rc.get("bookmark_threshold", 800)
        self.reverse_tags = config.get("reverse_tags", [])
        self.positive_tags = config.get("tag_search", {}).get("positive_tags", [])

    def run(self):
        print("\n开始排行榜检索")
        periods = self._get_periods_to_scan()
        if not periods:
            print("所有时间段已检索完毕")
            return

        for period_key in periods:
            self._scan_period(period_key)
            self.index.save()

        pending = self.index.get_pending_list()
        if pending:
            print(f"\n排行榜检索完成，{len(pending)} 篇待处理")

    def _get_periods_to_scan(self) -> list[str]:
        periods = self._generate_ranking_periods(back_weeks=520)
        unscanned = []
        for p in periods:
            if not self.index.is_ranking_period_scanned(p):
                unscanned.append(p)
        return unscanned

    def _generate_ranking_periods(self, back_weeks: int = 52) -> list[str]:
        today = datetime.now()
        periods = []
        for i in range(back_weeks):
            monday = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
            next_monday = monday + timedelta(days=7)
            date_param = next_monday.strftime("%Y%m%d")
            period_str = f"{monday.strftime('%Y-%m-%d')}~{(next_monday - timedelta(days=1)).strftime('%Y-%m-%d')}"
            periods.append(f"{date_param}|{period_str}")
        return periods

    def _scan_period(self, period_key: str):
        date_param, period_str = period_key.split("|")
        print(f"\n  检索时间段: {period_str}")

        try:
            novel_ids = self.api.get_ranking_ids(self.mode, date_param)
        except Exception as e:
            print(f"  排行获取失败: {e}")
            return

        if not novel_ids:
            print(f"  该时间段无排行数据")
            self.index.add_ranking_record(ScannedRecord(
                period_key=period_key, scan_type="ranking",
                scanned_at=datetime.now().isoformat(), novel_ids=[], downloaded=0, pending_ids=[]
            ))
            return

        print(f"  获取到 {len(novel_ids)} 篇排行榜作品")

        novel_ids = novel_ids[:self.top_n]
        downloaded = 0
        pending_ids = []

        for nid in novel_ids:
            if self.index.is_downloaded(nid):
                continue

            novel = self._fetch_novel_detail(nid)
            if not novel:
                continue

            if novel.bookmark_count > self.bookmark_threshold:
                self._download_with_series_check(novel)
                downloaded += 1
                print(f"    [收藏>{self.bookmark_threshold}] {novel.title}")
            else:
                if self.reverse_tags and any(rt in novel.tags for rt in self.reverse_tags):
                    self.index.add_pending(PendingItem(
                        novel_id=novel.id, title=novel.title,
                        matched_tags=[rt for rt in self.reverse_tags if rt in novel.tags],
                        url=novel.url, source="ranking"
                    ))
                    pending_ids.append(novel_id)
                    print(f"    [待处理-反向Tag] {novel.title}")
                elif self.positive_tags and any(pt in novel.tags for pt in self.positive_tags):
                    self._download_with_series_check(novel)
                    downloaded += 1
                    print(f"    [Tag匹配] {novel.title}")

        self.index.add_ranking_record(ScannedRecord(
            period_key=period_key, scan_type="ranking",
            scanned_at=datetime.now().isoformat(), novel_ids=novel_ids,
            downloaded=downloaded, pending_ids=pending_ids,
        ))

    def _fetch_novel_detail(self, novel_id: str) -> PixivNovel | None:
        try:
            return self.api.get_novel_detail(novel_id)
        except Exception as e:
            print(f"      {novel_id} 详情获取失败: {e}")
        return None

    def _download_with_series_check(self, novel: PixivNovel):
        decision, chapter_ids, series_info = self.judge.judge(novel)
        if decision == "merge":
            path = self.downloader.download_series(novel, series_info, chapter_ids)
            print(f"      [系列合并] {series_info.title} → {path}")
        else:
            path = self.downloader.download(novel)
            if path:
                print(f"      [下载] {novel.title} → {path}")
