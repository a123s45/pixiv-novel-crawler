import os
import random
import time
from typing import Optional

import requests


class PixivAuth:
    def __init__(self, config: dict):
        self.cookie = config["auth"]["cookie"]
        self.user_agent = config["auth"].get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        self._session: Optional[requests.Session] = None
        self._last_request = 0.0
        self.base_delay = config.get("download", {}).get("delay_seconds", 3)
        self.delay = self.base_delay
        self.min_delay = self.base_delay
        self.max_delay = 30
        self.success_count = 0
        self.proxy = self._resolve_proxy(config)

    def _resolve_proxy(self, config: dict) -> dict | None:
        proxy_url = config.get("proxy") or os.environ.get("HTTPS_PROXY") or os.environ.get("ALL_PROXY")
        if proxy_url:
            return {"http": proxy_url, "https": proxy_url}
        return None

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.cookies.set("PHPSESSID", self.cookie)
            self._session.headers.update(
                {
                    "User-Agent": self.user_agent,
                    "Referer": "https://www.pixiv.net/",
                    "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7",
                }
            )
            if self.proxy:
                self._session.proxies.update(self.proxy)
        return self._session

    def rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed + random.uniform(0, 0.5))
        self._last_request = time.time()

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        self.rate_limit()
        if "timeout" not in kwargs:
            kwargs["timeout"] = 30
        for attempt in range(3):
            resp = self.session.request(method, url, **kwargs)
            if resp.status_code == 429:
                self.delay = min(self.delay * 2, self.max_delay)
                self.success_count = 0
                wait = self.delay + random.uniform(1, 5)
                print(f"    限流 (429)，当前间隔 {self.delay:.0f}s，等待 {wait:.0f}s...")
                time.sleep(wait)
                continue
            if resp.status_code == 403 and attempt < 2:
                time.sleep(10)
                continue
            resp.raise_for_status()
            self.success_count += 1
            if self.success_count >= 20 and self.delay > self.min_delay:
                self.delay = max(self.delay * 0.8, self.min_delay)
                self.success_count = 0
                print(f"    降速至 {self.delay:.1f}s")
            return resp
        resp.raise_for_status()
        return resp

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)
