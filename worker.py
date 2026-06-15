import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from auth import PixivAuth
from pixiv_api import PixivAPI
from index_manager import IndexManager
from downloader import Downloader
from ai_client import AIClient
from series_judge import SeriesJudge
from tag_crawler import TagCrawler
from ranking_crawler import RankingCrawler
from evaluator import Evaluator
from translator import Translator
from archiver import Archiver


@dataclass
class CrawlerState:
    running: bool = False
    stop_flag: bool = False
    task_type: str = ""  # "ranking" or "tag"
    progress: float = 0.0
    current_item: str = ""
    log: list = field(default_factory=list)
    downloaded: int = 0
    total: int = 0


class CrawlerWorker:
    def __init__(self, config: dict):
        self.config = config
        self.state = CrawlerState()
        self._thread: Optional[threading.Thread] = None

    def start_ranking(self):
        if self.state.running:
            return
        self.state = CrawlerState(running=True, task_type="ranking")
        self._thread = threading.Thread(target=self._run_ranking, daemon=True)
        self._thread.start()

    def start_tag_search(self):
        if self.state.running:
            return
        self.state = CrawlerState(running=True, task_type="tag")
        self._thread = threading.Thread(target=self._run_tag_search, daemon=True)
        self._thread.start()

    def stop(self):
        self.state.stop_flag = True

    def _setup_post_processors(self, dl, ai):
        ev = Evaluator(ai, self.config)
        tr = Translator(ai, self.config)
        ar = Archiver(self.config)
        dl.set_post_processors(ev, tr, ar)

    def _run_ranking(self):
        try:
            auth = PixivAuth(self.config)
            api = PixivAPI(auth)
            index = IndexManager()
            dl = Downloader(api, index, self.config)
            ai = AIClient(self.config)
            self._setup_post_processors(dl, ai)
            judge = SeriesJudge(api, ai, index, self.config)
            tc = TagCrawler(api, index, dl, judge, self.config)
            rc = RankingCrawler(api, index, dl, judge, tc, self.config)

            periods = rc._get_periods_to_scan()
            self.state.total = len(periods)
            for i, period in enumerate(periods):
                if self.state.stop_flag:
                    self.state.log.append("已停止")
                    break
                self.state.current_item = period
                self.state.progress = i / max(len(periods), 1)
                rc._scan_period(period)
                index.save()
                self.state.downloaded = len(index.data["downloaded_ids"])

            self.state.progress = 1.0
            self.state.log.append("排行榜检索完成")
        except Exception as e:
            self.state.log.append(f"错误: {e}")
        finally:
            self.state.running = False

    def _run_tag_search(self):
        try:
            auth = PixivAuth(self.config)
            api = PixivAPI(auth)
            index = IndexManager()
            dl = Downloader(api, index, self.config)
            ai = AIClient(self.config)
            self._setup_post_processors(dl, ai)
            judge = SeriesJudge(api, ai, index, self.config)
            tc = TagCrawler(api, index, dl, judge, self.config)

            tc.run()

            self.state.log.append("Tag 检索完成")
            self.state.downloaded = len(index.data["downloaded_ids"])
        except Exception as e:
            self.state.log.append(f"错误: {e}")
        finally:
            self.state.running = False
