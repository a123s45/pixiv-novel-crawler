import json
import os
import re

import requests


class AIClient:
    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get("ai", {}).get("provider", "opencode")

    def _deepseek_call(self, prompt: str, max_tokens: int = 1024, temperature: float = 0) -> str:
        api_key = os.environ.get("DEEPSEEK_API_KEY") or self.config.get("ai", {}).get("api_key", "")
        if not api_key:
            return ""
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=60,
        )
        return resp.json()["choices"][0]["message"]["content"].strip()

    def judge_series(self, prompt: str, chapters_info=None) -> str:
        if self.provider == "deepseek":
            return self._deepseek_judge(prompt)
        return self._heuristic_judge(chapters_info)

    def _heuristic_judge(self, chapters_info) -> str:
        if not chapters_info or len(chapters_info) <= 1:
            return "B"
        titles = [c.title for c in chapters_info]
        sequential_pattern = re.compile(r"第[一二三四五六七八九十百千万\d]+[話話章节回部話]")
        has_sequential = any(sequential_pattern.search(t) for t in titles)
        if has_sequential and len(chapters_info) <= 20:
            return "A"
        if len(chapters_info) >= 10:
            return "A"
        return "B"

    def _deepseek_judge(self, prompt: str) -> str:
        api_key = os.environ.get("DEEPSEEK_API_KEY") or self.config.get("ai", {}).get("api_key", "")
        if not api_key:
            return self._heuristic_judge([])
        try:
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 10,
                    "temperature": 0,
                },
                timeout=30,
            )
            result = resp.json()["choices"][0]["message"]["content"].strip().upper()
            return result if result in ("A", "B") else "B"
        except Exception:
            return self._heuristic_judge([])

    def evaluate_quality(self, prompt: str) -> dict:
        result = self._deepseek_call(prompt, max_tokens=512, temperature=0)
        if not result:
            return {}
        try:
            start = result.find('{')
            end = result.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(result[start:end])
        except Exception:
            pass
        return {}

    def translate_text(self, prompt: str) -> str:
        return self._deepseek_call(prompt, max_tokens=4096, temperature=0.3)

    def detect_language(self, text: str) -> str:
        prompt = f"识别以下文本的语言，只回复语言代码（zh/ja/en/ko/其他）：\n\n{text[:500]}"
        result = self._deepseek_call(prompt, max_tokens=10, temperature=0)
        if result in ("zh", "ja", "en", "ko"):
            return result
        return "ja"

    def extract_glossary(self, text: str, source_lang: str) -> dict:
        prompt = f"""从以下{source_lang}小说开头部分提取所有人名/角色名，并给出中文译名建议。
输出JSON格式（严格JSON，不要多余文字）：
{{"names": [{{"original": "原文名字", "chinese": "中文译名", "type": "人物"}}]}}

原文：
{text[:2000]}"""
        result = self._deepseek_call(prompt, max_tokens=512, temperature=0)
        if not result:
            return {}
        try:
            start = result.find('{')
            end = result.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(result[start:end])
        except Exception:
            pass
        return {}
