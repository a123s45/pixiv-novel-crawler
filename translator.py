import os
import re

from models import PixivNovel


class Translator:
    def __init__(self, ai_client, config: dict):
        self.ai = ai_client
        self.prompt_template = config.get("ai", {}).get(
            "translation_prompt",
            "你是专业小说翻译。将以下所有语言翻译成中文。\n\n"
            "[人名对照表]\n{glossary}\n\n"
            "要求：\n"
            "1. 严格遵照人名对照表，不得改变\n"
            "2. 保持原作者行文风格和语气\n"
            "3. 中文流畅自然\n"
            "4. 专有名词首次出现可括号附注原文\n\n"
            "原文：\n{text}\n\n翻译："
        )

    def process(self, novel: PixivNovel, full_text: str) -> tuple:
        api_key = (self.ai.config.get("ai", {}).get("api_key", "")
                   or os.environ.get("DEEPSEEK_API_KEY", ""))
        if not api_key:
            return None, None
        lang = self.ai.detect_language(full_text)
        if lang == "zh":
            return None, None

        glossary_raw = self.ai.extract_glossary(full_text[:3000], lang)
        glossary_text = self._format_glossary(glossary_raw)

        segments = re.split(r'\n{2,}', full_text)
        translated = []
        for seg in segments:
            if not seg.strip():
                translated.append("")
                continue
            prompt = self.prompt_template.format(glossary=glossary_text, text=seg)
            result = self.ai.translate_text(prompt)
            translated.append(result if result else seg)

        translated_text = "\n\n".join(translated)

        output_dir = "translate_tmp"
        os.makedirs(output_dir, exist_ok=True)
        base = f"{self._safe_name(novel.title)}_{novel.id}"
        orig_path = os.path.join(output_dir, f"{base}_original.txt")
        trans_path = os.path.join(output_dir, f"{base}.txt")

        with open(orig_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        with open(trans_path, "w", encoding="utf-8") as f:
            f.write(translated_text)

        return orig_path, trans_path

    def _format_glossary(self, glossary: dict) -> str:
        if not glossary or "names" not in glossary:
            return "无"
        lines = []
        for n in glossary.get("names", []):
            orig = n.get("original", "")
            ch = n.get("chinese", orig)
            lines.append(f"{orig} → {ch}")
        return "\n".join(lines)

    def _safe_name(self, name: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', "_", name)[:80]
