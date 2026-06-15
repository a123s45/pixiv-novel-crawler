import json
import re
from urllib.parse import quote, urlencode

from auth import PixivAuth
from models import PixivNovel, SeriesInfo, ChapterInfo


class PixivAPI:
    BASE = "https://www.pixiv.net"

    def __init__(self, auth: PixivAuth):
        self.auth = auth

    def search_novels(self, tag: str, page: int = 1, limit: int = 48, sort: str = "date_desc") -> list[PixivNovel]:
        order = "date_d" if sort == "date_desc" else "date"
        offset = (page - 1) * limit
        url = f"{self.BASE}/ajax/search/novels/{quote(tag, safe='')}"
        params = {"order": order, "limit": limit, "offset": offset}
        resp = self.auth.get(f"{url}?{urlencode(params)}")
        data = resp.json()

        novels = []
        for item in data.get("body", {}).get("novel", {}).get("data", []):
            if self._is_valid_novel(item):
                novels.append(self._parse_novel(item))
        return novels

    def get_novel_detail(self, novel_id: str) -> PixivNovel:
        url = f"{self.BASE}/ajax/novel/{novel_id}"
        resp = self.auth.get(url)
        data = resp.json().get("body", {})

        tags = [t["tag"] for t in data.get("tags", {}).get("tags", [])]
        return PixivNovel(
            id=str(data["id"]),
            title=data.get("title", ""),
            tags=tags,
            user_id=str(data.get("userId", "")),
            user_name=data.get("userName", ""),
            bookmark_count=data.get("bookmarkCount", 0),
            word_count=data.get("wordCount", 0),
            text_count=data.get("textCount", 0),
            create_date=data.get("createDate", ""),
            upload_date=data.get("uploadDate", ""),
            description=data.get("description", ""),
            series_id=str(data["seriesId"]) if data.get("seriesId") else None,
            series_title=data.get("seriesTitle"),
            language=self._detect_language(data.get("title", "")),
            url=f"{self.BASE}/novel/show.php?id={novel_id}",
        )

    def get_novel_text(self, novel_id: str) -> str:
        url = f"{self.BASE}/ajax/novel/{novel_id}"
        resp = self.auth.get(url)
        content = resp.json().get("body", {}).get("content", "")
        if content:
            import html as html_mod
            content = html_mod.unescape(content)
            content = re.sub(r'<br\s*/?>', '\n', content)
            content = re.sub(r'<[^>]+>', '', content)
            content = re.sub(r'\n{3,}', '\n\n', content)
        return content.strip()

    def get_series_info(self, series_id: str) -> SeriesInfo:
        url = f"{self.BASE}/ajax/novel/series/{series_id}"
        resp = self.auth.get(url)
        data = resp.json().get("body", {})

        chapters = []
        for item in data.get("seriesContent", []):
            chapters.append(ChapterInfo(
                id=str(item["id"]),
                title=item.get("title", ""),
                tags=[t["tag"] for t in item.get("tags", [])],
                order=item.get("order", 0),
                description="",
            ))

        return SeriesInfo(
            id=str(data["id"]),
            title=data.get("title", ""),
            caption=data.get("caption", ""),
            tags=[t.get("tag", "") for t in data.get("tags", [])],
            content_count=data.get("contentCount", 0),
            chapters=chapters,
        )

    def get_chapter_preview(self, novel_id: str, max_chars: int = 200) -> str:
        text = self.get_novel_text(novel_id)
        text = re.sub(r"\s+", "", text)
        return text[:max_chars]

    def search_tags(self, keyword: str) -> list[dict]:
        url = f"{self.BASE}/ajax/search/tags/{quote(keyword, safe='')}"
        resp = self.auth.get(url)
        data = resp.json()
        body = data.get("body", {})

        translations = body.get("tagTranslation", {})
        pixpedia = body.get("pixpedia", {})
        tag_names = []
        seen = set()

        def add(name):
            if name and name not in seen:
                seen.add(name)
                tag_names.append(name)

        add(body.get("tag", ""))
        if pixpedia.get("parentTag"):
            add(pixpedia["parentTag"])
        for t in pixpedia.get("siblingsTags", []):
            add(t)
        for t in pixpedia.get("childrenTags", []):
            add(t)
        for bc in body.get("breadcrumbs", {}).get("successor", []):
            add(bc.get("tag", ""))

        results = []
        for name in tag_names:
            trans = translations.get(name, {})
            results.append({
                "tag": name,
                "translation": trans.get("zh", "") or trans.get("en", "") or trans.get("zh_tw", ""),
            })
        return results

    def get_favorite_tags(self) -> list[str]:
        url = f"{self.BASE}/ajax/search/tags/%E4%BA%BA"
        resp = self.auth.get(url)
        return resp.json().get("body", {}).get("myFavoriteTags", [])

    def get_ranking_ids(self, mode: str, date: str) -> list[str]:
        ids = []
        seen = set()
        for page in (1, 2):
            try:
                ids.extend(self._fetch_ranking_page(mode, date, page, seen))
            except Exception as e:
                pass
        return ids

    def _fetch_ranking_page(self, mode: str, date: str, page: int, seen: set) -> list[str]:
        url = f"{self.BASE}/novel/ranking.php"
        params = {"mode": mode, "date": date, "p": page}
        resp = self.auth.get(f"{url}?{urlencode(params)}")
        match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        if not match:
            return []

        data = json.loads(match.group(1))
        rank_a = data.get("props", {}).get("pageProps", {}).get("assign", {}).get("display_a", {}).get("rank_a", [])
        result = []
        for item in rank_a:
            nid = str(item.get("id", ""))
            if nid and nid not in seen:
                seen.add(nid)
                result.append(nid)
        return result

    def _is_valid_novel(self, item: dict) -> bool:
        return item.get("id") and item.get("title")

    def _parse_novel(self, item: dict) -> PixivNovel:
        tags = [t.get("tag", "") for t in item.get("tags", [])]
        return PixivNovel(
            id=str(item["id"]),
            title=item.get("title", ""),
            tags=tags,
            user_id=str(item.get("userId", "")),
            user_name=item.get("userName", ""),
            bookmark_count=item.get("bookmarkCount", 0),
            word_count=item.get("wordCount", 0),
            text_count=item.get("textCount", 0),
            create_date=item.get("createDate", ""),
            upload_date=item.get("uploadDate", ""),
            description=item.get("description", ""),
            series_id=str(item["seriesId"]) if item.get("seriesId") else None,
            series_title=item.get("seriesTitle"),
            language=self._detect_language(item.get("title", "")),
            url=f"{self.BASE}/novel/show.php?id={item['id']}",
        )

    def _detect_language(self, text: str) -> str:
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh"
        if re.search(r"[\uac00-\ud7af]", text):
            return "ko"
        return "ja"
