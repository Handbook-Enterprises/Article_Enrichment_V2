import logging
import asyncio
from typing import Dict, List
from urllib.parse import urlparse

import httpx


def _guess_type_from_url(url: str) -> str:
    path = urlparse(url or "").path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"):
        if path.endswith(ext):
            return "image"
    for ext in (".mp4", ".webm", ".mov", ".m4v"):
        if path.endswith(ext):
            return "video"
    if path.endswith(".pdf"):
        return "resource"
    return "resource"


def _browser_headers(url: str) -> Dict[str, str]:
    parsed = urlparse(url or "")
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else "https://example.com"
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": origin,
    }


# Synchronous validator removed; we use async concurrent HEAD/GET by default.


async def _is_url_available_async(client: httpx.AsyncClient, url: str, type_hint: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    acceptable_types = {
        "image": ("image/", "application/octet-stream"),
        "video": ("video/", "text/html", "application/octet-stream"),
        "resource": ("text/html", "application/pdf", "application/json"),
    }
    expected = acceptable_types.get(type_hint, ("text/html",))
    guessed = _guess_type_from_url(url)
    headers = _browser_headers(url)
    try:
        # Run HEAD and a lightweight GET concurrently; succeed if either matches expected type
        head_task = client.head(url, headers=headers)
        get_task = client.get(url, headers={**headers, "Range": "bytes=0-64"})
        head_resp, get_resp = await asyncio.gather(head_task, get_task, return_exceptions=True)

        # Evaluate HEAD
        if isinstance(head_resp, httpx.Response):
            if 200 <= head_resp.status_code < 300:
                ctype = (head_resp.headers.get("Content-Type") or "").lower()
                if any(ctype.startswith(t) for t in expected):
                    return True
            elif head_resp.status_code in (401, 403) and guessed == type_hint:
                return True

        # Evaluate GET
        if isinstance(get_resp, httpx.Response):
            if 200 <= get_resp.status_code < 300:
                ctype = (get_resp.headers.get("Content-Type") or "").lower()
                if any(ctype.startswith(t) for t in expected):
                    return True
            elif get_resp.status_code in (401, 403) and guessed == type_hint:
                return True
    except Exception:
        return False
    return False


async def _filter_candidates_async(candidates: Dict) -> Dict:
    hero = candidates.get("hero", [])
    context = candidates.get("context", [])
    links = candidates.get("links", [])

    timeout = httpx.Timeout(connect=2.0, read=2.0, write=2.0, pool=2.0)
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, limits=limits) as client:
        hero_tasks = [asyncio.create_task(_is_url_available_async(client, a.get("url"), "image")) for a in hero]
        ctx_tasks = [asyncio.create_task(_is_url_available_async(client, a.get("url"), a.get("type", "image"))) for a in context]
        link_tasks = [asyncio.create_task(_is_url_available_async(client, l.get("url"), "resource")) for l in links]

        hero_results = await asyncio.gather(*hero_tasks, return_exceptions=True) if hero_tasks else []
        ctx_results = await asyncio.gather(*ctx_tasks, return_exceptions=True) if ctx_tasks else []
        link_results = await asyncio.gather(*link_tasks, return_exceptions=True) if link_tasks else []

    avail_hero = [a for a, ok in zip(hero, hero_results) if ok is True]
    avail_context = [a for a, ok in zip(context, ctx_results) if ok is True]
    avail_links = [l for l, ok in zip(links, link_results) if ok is True]

    removed_hero = len(hero) - len(avail_hero)
    removed_context = len(context) - len(avail_context)
    removed_links = len(links) - len(avail_links)
    logging.info(
        f"Asset availability filter | removed hero={removed_hero} | removed context={removed_context} | removed links={removed_links}"
    )

    return {
        "hero": avail_hero or hero,
        "context": avail_context or context,
        "links": avail_links or links,
    }


def filter_candidates_by_availability(candidates: Dict) -> Dict:
    try:
        return asyncio.run(_filter_candidates_async(candidates))
    except Exception as e:
        logging.warning(f"Async validation failed; returning unfiltered candidates: {e}")
        return candidates