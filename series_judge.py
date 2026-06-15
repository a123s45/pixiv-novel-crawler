from pixiv_api import PixivAPI
from models import PixivNovel, SeriesJudgment
from index_manager import IndexManager
from ai_client import AIClient


class SeriesJudge:
    def __init__(self, api: PixivAPI, ai: AIClient, index: IndexManager, config: dict):
        self.api = api
        self.ai = ai
        self.index = index
        self.config = config

    def judge(self, novel: PixivNovel) -> tuple[str, list[str], object]:
        if not novel.series_id:
            return "individual", [novel.id], None

        cached = self.index.get_series_judgment(novel.series_id)
        if cached:
            if cached["decision"] == "merge":
                series_info = self.api.get_series_info(novel.series_id)
                chapter_ids = [c.id for c in series_info.chapters]
                return "merge", chapter_ids, series_info
            return "individual", [novel.id], None

        series_info = self.api.get_series_info(novel.series_id)
        for ch in series_info.chapters:
            if not ch.description:
                try:
                    detail = self.api.get_novel_detail(ch.id)
                    ch.description = detail.description[:200] if detail.description else ""
                except Exception:
                    ch.description = ""

        prompt = self._build_prompt(series_info)
        result = self.ai.judge_series(prompt, series_info.chapters)

        judgment = SeriesJudgment(
            series_id=novel.series_id,
            decision="merge" if result == "A" else "individual",
            reason=f"AI 判断: {'连续故事需合并' if result == 'A' else '独立短篇合集'}",
        )
        self.index.save_series_judgment(judgment)

        if judgment.decision == "merge":
            chapter_ids = [c.id for c in series_info.chapters]
            return "merge", chapter_ids, series_info
        else:
            return "individual", [novel.id], None

    def _build_prompt(self, series_info) -> str:
        template = self.config.get("ai", {}).get(
            "series_judge_prompt",
            "判断以下 Pixiv 小说系列属于连续故事(A)还是独立短篇合集(B)",
        )

        chapters_lines = []
        for ch in series_info.chapters[:30]:
            tags_str = ", ".join(ch.tags[:5])
            desc = ch.description[:150] if ch.description else ""
            line = f"  {ch.order}. {ch.title}"
            if tags_str:
                line += f" [Tag: {tags_str}]"
            if desc:
                line += f" → {desc}"
            chapters_lines.append(line)

        if len(series_info.chapters) > 30:
            chapters_lines.append(f"  ... 共 {len(series_info.chapters)} 章")

        return template.format(
            series_title=series_info.title,
            series_caption=series_info.caption[:500] if series_info.caption else "",
            chapters_info="\n".join(chapters_lines),
        )
