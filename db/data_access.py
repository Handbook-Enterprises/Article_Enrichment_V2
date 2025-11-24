import sqlite3
from pathlib import Path
from typing import Dict, List


def load_article(article_path: str) -> str:
    return Path(article_path).read_text(encoding="utf-8")


def load_keywords(keywords_path: str) -> List[str]:
    raw = Path(keywords_path).read_text(encoding="utf-8")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def load_brand_rules(brand_rules_path: str) -> str:
    return Path(brand_rules_path).read_text(encoding="utf-8")


def _rows_to_dicts(cursor) -> List[Dict]:
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def load_media_db(media_db_path: str) -> Dict[str, List[Dict]]:
    conn = sqlite3.connect(media_db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, url, title, description, tags FROM images")
    images = _rows_to_dicts(cur)
    cur.execute("SELECT id, url, title, description, tags FROM videos")
    videos = _rows_to_dicts(cur)
    conn.close()
    return {"images": images, "videos": videos}


def load_links_db(links_db_path: str) -> List[Dict]:
    conn = sqlite3.connect(links_db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, url, title, description, topic_tags, type FROM resources"
    )
    links = _rows_to_dicts(cur)
    conn.close()
    return links