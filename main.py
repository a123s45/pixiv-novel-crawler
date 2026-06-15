import os
import sys
import io

# 解决 Windows 终端 GBK 编码无法打印 Unicode 字符（❤♡等）的问题
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

try:
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import yaml

from auth import PixivAuth
from pixiv_api import PixivAPI
from index_manager import IndexManager
from downloader import Downloader
from ai_client import AIClient
from series_judge import SeriesJudge
from tag_crawler import TagCrawler
from ranking_crawler import RankingCrawler
from pending_handler import PendingHandler


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_config(config: dict) -> bool:
    if not config.get("auth", {}).get("cookie"):
        print("错误: config.yaml 中 auth.cookie 为空，请填写 PHPSESSID")
        return False

    if not config.get("tag_search", {}).get("positive_tags") and not config.get("ranking", {}).get("enabled"):
        print("错误: 未启用排行榜且未配置 Tag，没有任务可执行")
        return False

    return True


def main():
    config = load_config()
    if not check_config(config):
        return

    index = IndexManager()

    auth = PixivAuth(config)
    api = PixivAPI(auth)
    downloader = Downloader(api, index, config)
    ai = AIClient(config)
    judge = SeriesJudge(api, ai, index, config)
    tag_crawler = TagCrawler(api, index, downloader, judge, config)
    ranking_crawler = RankingCrawler(api, index, downloader, judge, tag_crawler, config)
    pending_handler = PendingHandler(index)

    print("=" * 50)
    print("Pixiv 小说爬虫")
    print("=" * 50)

    ranking_enabled = config.get("ranking", {}).get("enabled", False)
    tags = config.get("tag_search", {}).get("positive_tags", [])

    print(f"排行榜检索: {'启用' if ranking_enabled else '禁用'}")
    print(f"Tag 检索: {', '.join(tags) if tags else '无'}")
    print(f"反向 Tag: {', '.join(config.get('reverse_tags', [])) or '无'}")
    print(f"输出目录: {config['download']['output_dir']}")
    print()

    if ranking_enabled:
        ranking_crawler.run()  # 排行榜检索（完成后自动启动 Tag 检索）
    elif tags:
        # 仅 Tag 检索模式（排行榜未启用）
        tag_crawler.run()

    pending = pending_handler.show_and_process()
    for item in pending:
        try:
            novel = api.get_novel_detail(item.novel_id)
            decision, chapter_ids, series_info = judge.judge(novel)
            if decision == "merge":
                path = downloader.download_series(novel, series_info, chapter_ids)
                print(f"  [下载] {series_info.title} → {path}")
            else:
                path = downloader.download(novel)
                if path:
                    print(f"  [下载] {novel.title} → {path}")
            index.remove_pending(item.novel_id)
        except Exception as e:
            print(f"  下载失败 {item.novel_id}: {e}")

    print("\n全部任务完成")


if __name__ == "__main__":
    main()
