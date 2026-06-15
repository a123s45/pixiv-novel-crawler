from index_manager import IndexManager
from models import PendingItem


class PendingHandler:
    def __init__(self, index: IndexManager):
        self.index = index

    def show_and_process(self) -> list[PendingItem]:
        items = self.index.get_pending_list()
        if not items:
            print("没有待处理作品。")
            return []

        print(f"\n{'=' * 60}")
        print(f"待处理作品清单（共 {len(items)} 篇）")
        print(f"{'=' * 60}")

        for i, item in enumerate(items, 1):
            print(f"[{i}] {item.title} ({item.novel_id})")
            print(f"    Tag: {', '.join(item.matched_tags[:5])}")
            print(f"    来源: {item.source}")
            print(f"    链接: {item.url}")
            print()

        to_download = []
        while True:
            cmd = input("\n操作: [序号]下载  [A]全部下载  [S]全部跳过  [Q]退出查看\n> ").strip().lower()

            if cmd == "a":
                to_download = items[:]
                break
            elif cmd == "s":
                break
            elif cmd == "q":
                break
            elif cmd.isdigit():
                idx = int(cmd) - 1
                if 0 <= idx < len(items):
                    to_download.append(items[idx])
                    print(f"已标记: {items[idx].title}")
                else:
                    print("序号无效")
            else:
                print("无效输入")

        return to_download
