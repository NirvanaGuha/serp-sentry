"""SERP providers behind one interface. Each returns the organic top-N as
[{position, domain, url, title}]. Parse functions are pure (unit-tested);
HTTP lives only in fetch_top.

Supported:
  serper   — serper.dev  (default; 2,500 free searches, no card)
  serpapi  — serpapi.com (100 free/month)
"""
import os
from urllib.parse import urlparse

import requests


def domain_of(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def parse_serper(data: dict, top_n: int) -> list[dict]:
    out = []
    for r in (data.get("organic") or [])[:top_n]:
        url = r.get("link", "")
        out.append({"position": r.get("position", len(out) + 1),
                    "domain": domain_of(url), "url": url,
                    "title": r.get("title", "")})
    return out


def parse_serpapi(data: dict, top_n: int) -> list[dict]:
    out = []
    for r in (data.get("organic_results") or [])[:top_n]:
        url = r.get("link", "")
        out.append({"position": r.get("position", len(out) + 1),
                    "domain": domain_of(url), "url": url,
                    "title": r.get("title", "")})
    return out


def provider_ready(serp_cfg: dict) -> tuple[bool, str]:
    provider = (serp_cfg.get("provider") or "serper").lower()
    if provider not in ("serper", "serpapi"):
        return False, f"unknown serp.provider '{provider}' (use serper or serpapi)"
    key_env = serp_cfg.get("api_key_env") or "SERP_API_KEY"
    if not os.environ.get(key_env):
        signup = {"serper": "https://serper.dev (2,500 free searches)",
                  "serpapi": "https://serpapi.com (100 free/month)"}[provider]
        return False, f"{key_env} not set — get a free key at {signup}"
    return True, f"{provider} (key via {key_env})"


def fetch_top(serp_cfg: dict, keyword: str, gl: str = "us", hl: str = "en",
              top_n: int = 10) -> list[dict]:
    provider = (serp_cfg.get("provider") or "serper").lower()
    key = os.environ[serp_cfg.get("api_key_env") or "SERP_API_KEY"]

    if provider == "serper":
        r = requests.post("https://google.serper.dev/search",
                          headers={"X-API-KEY": key,
                                   "Content-Type": "application/json"},
                          json={"q": keyword, "gl": gl, "hl": hl,
                                "num": max(top_n, 10)},
                          timeout=30)
        r.raise_for_status()
        return parse_serper(r.json(), top_n)

    if provider == "serpapi":
        r = requests.get("https://serpapi.com/search.json",
                         params={"engine": "google", "q": keyword, "gl": gl,
                                 "hl": hl, "num": max(top_n, 10),
                                 "api_key": key},
                         timeout=30)
        r.raise_for_status()
        return parse_serpapi(r.json(), top_n)

    raise ValueError(f"unknown serp provider: {provider}")
