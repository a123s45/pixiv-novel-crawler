import os

from models import PixivNovel, QualityResult


class Evaluator:
    def __init__(self, ai_client, config: dict):
        self.ai = ai_client
        self.threshold = config.get("ai", {}).get("quality_check_threshold", 500)
        self.prompt_template = config.get("ai", {}).get(
            "quality_eval_prompt",
            "你是一个Pixiv小说质量评估专家。评估以下小说：\n"
            "标题：{title}\nTag：{tags}\n收藏数：{bookmark_count}\n总字数：{word_count}\n\n"
            "正文（开头1500字+结尾1500字）：\n{text_sample}\n\n"
            '输出JSON：{{"is_completed":true/false/null,"has_advertisement":true/false,'
            '"requires_payment":true/false,'
            '"tag_fraud":{{"exists":true/false,"fraud_tags":[],"explanation":""}},'
            '"quality_score":0-100,"summary":"一句话简介","reason":"评估说明"}}'
        )

    def evaluate(self, novel: PixivNovel, full_text: str) -> QualityResult:
        text_len = len(full_text)
        if text_len < 3000:
            return QualityResult(
                novel_id=novel.id, title=novel.title,
                rejected=True, reasons=["文本过短（不足3000字）"],
                words_checked=text_len,
            )

        # 没有 API Key 时跳过 AI 质检，直接归档
        api_key = (self.ai.config.get("ai", {}).get("api_key", "")
                   or os.environ.get("DEEPSEEK_API_KEY", ""))
        if not api_key:
            return QualityResult(
                novel_id=novel.id, title=novel.title, rejected=False,
                words_checked=text_len,
            )

        head = full_text[:1500]
        tail = full_text[-1500:] if text_len > 1500 else ""
        sample = f"【开头部分】\n{head}\n\n【结尾部分】\n{tail}"

        prompt = self._build_prompt(novel, sample)
        raw = self.ai.evaluate_quality(prompt)
        result = self._parse_result(novel, raw)
        result.words_checked = text_len
        return result

    def _build_prompt(self, novel: PixivNovel, sample: str) -> str:
        tags = ", ".join(novel.tags)
        return self.prompt_template.format(
            title=novel.title, tags=tags,
            bookmark_count=novel.bookmark_count,
            word_count=novel.word_count,
            text_sample=sample,
        )

    def _parse_result(self, novel: PixivNovel, raw: dict) -> QualityResult:
        r = QualityResult(novel_id=novel.id, title=novel.title, rejected=False)

        if not raw:
            r.rejected = True
            r.reasons = ["AI 质检失败（API 返回为空）"]
            return r

        r.is_completed = raw.get("is_completed", True)
        if r.is_completed is None:
            r.is_completed = True
        r.has_advertisement = raw.get("has_advertisement", False)
        r.requires_payment = raw.get("requires_payment", False)
        r.quality_score = raw.get("quality_score", 50)
        r.summary = raw.get("summary", "")

        tf = raw.get("tag_fraud", {})
        if isinstance(tf, dict):
            r.tag_fraud = tf.get("exists", False)
            r.fraud_tags = tf.get("fraud_tags", [])
        else:
            r.tag_fraud = bool(tf)

        if r.tag_fraud:
            r.rejected = True
            detail = ", ".join(r.fraud_tags) if r.fraud_tags else "Tag与内容明显不符"
            r.reasons = [f"Tag欺诈: {detail}"]

        if novel.bookmark_count < self.threshold:
            flags = sum([r.has_advertisement, r.requires_payment, not r.is_completed])
            if r.quality_score < 50 or flags >= 2:
                r.rejected = True
                reasons = []
                if r.quality_score < 50:
                    reasons.append(f"质量评分偏低({r.quality_score})")
                if r.has_advertisement:
                    reasons.append("包含引流广告/推广")
                if r.requires_payment:
                    reasons.append("需要付费平台解锁")
                if not r.is_completed:
                    reasons.append("未完结")
                r.reasons = reasons

        return r
