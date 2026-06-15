from datetime import datetime, timedelta

from auth import PixivAuth
from pixiv_api import PixivAPI
from models import ScannedRecord, PixivNovel, PendingItem
from index_manager import IndexManager
from downloader import Downloader
from series_judge import SeriesJudge
from tag_crawler import TagCrawler


class RankingCrawler:
    def __init__(self, api: PixivAPI, index: IndexManager, downloader: Downloader,
                 judge: SeriesJudge, tag_crawler: TagCrawler, config: dict):
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
        self.negative_tags = config.get("tag_search", {}).get("negative_tags", [])
        self.reverse_tags = config.get("reverse_tags", [])
        self.positive_tags = config.get("tag_search", {}).get("positive_tags", [])

    def run(self):
        print("\n开始排行榜检索")
        periods = self._get_periods_to_scan()
        if not periods:
            print("所有时间段已检索完毕")
        else:
            for period_key in periods:
                self._scan_period(period_key)
                self.index.save()
                self._update_progress_marker(period_key)

        pending = self.index.get_pending_list()
        if pending:
            print(f"\n排行榜检索完成，{len(pending)} 篇待处理")

        # 排行榜完成后自动开始正向 Tag 检索
        if self.positive_tags:
            print("\n" + "=" * 50)
            print("排行榜完成，开始正向 Tag 检索")
            print("=" * 50)
            self.tag_crawler.run()

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

            # ===== 最高优先级：排除Tag（负面Tag）========
            if self.negative_tags and any(nt.lower() == t.lower() for nt in self.negative_tags for t in novel.tags):
                continue  # 直接跳过，不记录（精确匹配）

            # ===== 判断是否应该下载 =====
            should_download = False
            if novel.bookmark_count >= self.bookmark_threshold:
                should_download = True
                reason = f"收藏>={self.bookmark_threshold}"
            elif self.positive_tags and any(pt.lower() == t.lower() for pt in self.positive_tags for t in novel.tags):
                should_download = True
                reason = "Tag匹配"
            else:
                # 收藏不达标且无正向Tag匹配 → 跳过
                continue

            # ===== 反向Tag处理 =====
            if self.reverse_tags and any(rt.lower() == t.lower() for rt in self.reverse_tags for t in novel.tags):
                # 命中反向Tag → 加入待处理（不自动下载）
                matched = [rt for rt in self.reverse_tags if any(rt.lower() == t.lower() for t in novel.tags)]
                self.index.add_pending(PendingItem(
                    novel_id=novel.id, title=novel.title,
                    matched_tags=matched,
                    url=novel.url, source="ranking"
                ))
                pending_ids.append(novel.id)
                print(f"    [待处理-反向Tag] {novel.title} (收藏:{novel.bookmark_count})")
                continue  # 不自动下载，等待人工审核

            # ===== 正常下载 =====
            try:
                self._download_with_series_check(novel)
                downloaded += 1
                print(f"    [{reason}] {novel.title} (收藏:{novel.bookmark_count})")
            except Exception as e:
                print(f"    [下载失败] {novel.title}: {type(e).__name__}")
                # 继续处理下一部，不中断整个扫描

        self.index.add_ranking_record(ScannedRecord(
            period_key=period_key, scan_type="ranking",
            scanned_at=datetime.now().isoformat(), novel_ids=novel_ids,
            downloaded=downloaded, pending_ids=pending_ids,
        ))

    def _update_progress_marker(self, last_period_key: str):
        """更新 SCAN_PROGRESS.md 进度标记"""
        try:
            scanned = self.index.data.get("ranking_scanned", [])
            total_dl = len(self.index.data.get("downloaded_ids", []))
            pending = self.index.data.get("pending_list", [])

            # 格式化已完成的周排行
            done_lines = []
            for s in reversed(scanned[-20:]):  # 只显示最近20条
                period = s["period_key"][:25]
                dl = s.get("downloaded", 0)
                done_lines.append(f"- [x] {period} (下载{dl}篇)")

            if len(scanned) > 20:
                done_lines.insert(0, f"- ... 还有 {len(scanned) - 20} 期已扫描 (共{len(scanned)}期)")

            # 待处理
            pending_lines = []
            for p in pending:
                pending_lines.append(f"- {p['title'][:40]} [{','.join(p['matched_tags'][:2])}]")

            content = f"""# 排行榜扫描进度跟踪
> 自动生成 | 下次运行自动跳过已标记时间段

## 状态

- 扫描进度: **进行中**
- 已扫描: **{len(scanned)} 期**
- 已下载: **{total_dl} 篇**
- 待处理: **{len(pending)} 篇**
- 当前扫描: **{last_period_key[:25]}**
- 最后更新: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}

## 已完成的周排行（最近20期）

{chr(10).join(done_lines)}

## 待处理作品（ntr）

{chr(10).join(pending_lines) if pending_lines else "无"}

## 全部期数

共 {len(scanned)} 期，最早 {scanned[0]['period_key'][:25] if scanned else 'N/A'}
"""
            path = os.path.join(os.path.dirname(__file__), "SCAN_PROGRESS.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            pass  # 标记文件更新失败不影响主流程

    def _fetch_novel_detail(self, novel_id: str) -> PixivNovel | None:
        try:
            return self.api.get_novel_detail(novel_id)
        except Exception as e:
            print(f"      {novel_id} 详情获取失败: {e}")
        return None

    def _download_with_series_check(self, novel: PixivNovel):
        try:
            decision, chapter_ids, series_info = self.judge.judge(novel)
        except Exception as e:
            print(f"      [系列判断失败] {novel.title}: {e}")
            # 降级为单篇下载
            decision = "individual"
            chapter_ids = []
            series_info = None

        try:
            if decision == "merge":
                path = self.downloader.download_series(novel, series_info, chapter_ids)
                print(f"      [系列合并] {series_info.title} → {path}")
            else:
                path = self.downloader.download(novel)
                if path:
                    print(f"      [下载] {novel.title} → {path}")
        except Exception as e:
            print(f"      [下载异常] {novel.title}: {type(e).__name__}")
