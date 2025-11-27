import re
import difflib
import logging
from typing import Dict, List, Tuple, Set

SECTION_RE = re.compile(r"^(#{1,6})\s+(.*)$")

# Stopwords for initialism generation
STOPWORDS = {"and", "of", "to", "for", "the", "a", "an", "in", "on", "with"}


# Normalize whitespace and lowercase text for consistent comparisons
def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


# Tokenize text into alphanumeric or hyphen-separated tokens
def tokenize(s: str) -> List[str]:
    s = normalize_text(s)
    return re.findall(r"[a-zA-Z0-9\-]+", s)


# Build an initialism from a phrase, skipping common stopwords
def initialism(phrase: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", phrase.lower())
    letters = [p[0] for p in parts if p not in STOPWORDS and p]
    return "".join(letters)


# Detect and map acronym ↔ longform pairs present in text
def extract_acronym_pairs(text: str) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    # longform (ACRONYM)
    for longform, acro in re.findall(r"\b([A-Za-z][A-Za-z \-]{2,})\s*\(([A-Z]{2,6})\)", text or ""):
        lf = normalize_text(longform)
        acr = acro.lower()
        if initialism(lf) == acr:
            pairs[acr] = lf
            pairs[lf] = acr
    # ACRONYM (longform)
    for acro, longform in re.findall(r"\b([A-Z]{2,6})\s*\(([A-Za-z][A-Za-z \-]{2,})\)", text or ""):
        lf = normalize_text(longform)
        acr = acro.lower()
        if initialism(lf) == acr:
            pairs[acr] = lf
            pairs[lf] = acr
    return pairs


# Collect tokens from media and link metadata for relevance scoring
def collect_asset_tokens(media: Dict[str, List[Dict]], links: List[Dict]) -> Set[str]:
    bucket: List[str] = []
    for img in media.get("images", []):
        bucket += tokenize(img.get("title", ""))
        bucket += tokenize(img.get("description", ""))
        bucket += tokenize(img.get("tags", ""))
    for vid in media.get("videos", []):
        bucket += tokenize(vid.get("title", ""))
        bucket += tokenize(vid.get("description", ""))
        bucket += tokenize(vid.get("tags", ""))
    for r in links:
        bucket += tokenize(r.get("title", ""))
        bucket += tokenize(r.get("description", ""))
        bucket += tokenize(r.get("topic_tags", ""))
    return set(bucket)


# Generate keyword variants using normalization, pluralization, acronyms, and fuzzy matching
def keyword_variants_dynamic(kw: str, article_tokens: List[str], asset_tokens: Set[str], pairs: Dict[str, str]) -> List[str]:
    base = normalize_text(kw)
    tokens = re.findall(r"[a-z0-9]+", base)
    hyphen = "-".join(tokens) if tokens else base
    spaced = " ".join(tokens) if tokens else base
    joined = "".join(tokens) if tokens else base

    variants = {base, hyphen, spaced, joined}

    # pluralization (simple, safe)
    if tokens:
        last = tokens[-1]
        if last.endswith("y") and len(last) > 1:
            variants.add(" ".join(tokens[:-1] + [last[:-1] + "ies"]))
        else:
            variants.add(" ".join(tokens + ["s"]))

    # acronym \u2194 longform from text
    if base in pairs:
        variants.add(pairs[base])
    acro = initialism(base)
    if acro and (acro in asset_tokens or acro in article_tokens):
        variants.add(acro)

    # fuzzy near-matches from asset/article tokens using difflib
    universe = set(asset_tokens) | set(article_tokens)
    compact_base = base.replace(" ", "")
    for cand in universe:
        if len(cand) < 3:
            continue
        ratio = difflib.SequenceMatcher(None, cand, compact_base).ratio()
        if ratio >= 0.82:
            variants.add(cand)

    return sorted({normalize_text(v) for v in variants if 1 <= len(v) <= 60})


def build_article_profile(markdown: str) -> Dict:
    lines = markdown.splitlines()
    sections: List[Dict] = []
    current = {"heading": None, "level": None, "content": []}
    for line in lines:
        m = SECTION_RE.match(line)
        if m:
            if current["heading"] is not None:
                sections.append(current)
            current = {"heading": m.group(2), "level": len(m.group(1)), "content": []}
        else:
            current["content"].append(line)
    if current["heading"] is not None:
        sections.append(current)

    all_text = markdown
    return {
        "sections": sections,
        "headings": [s["heading"] for s in sections],
        "tokens": tokenize(all_text),
    }


# Compute a relevance score overlap
def _score_asset(title: str, desc: str, tags: str, kset: Set[str], section_tokens: List[str]) -> float:
    tt = tokenize(title or "") + tokenize(desc or "") + tokenize(tags or "")
    tset = set(tt)
    overlap_kw = len([t for t in tset if any((t in kv) or (kv in t) for kv in kset)])
    overlap_article = len(set(section_tokens) & tset)
    score = 2.0 * overlap_kw + 1.0 * overlap_article
    title_hits = len(set(tokenize(title or "")) & kset)
    desc_hits = len(set(tokenize(desc or "")) & kset)
    if title_hits and desc_hits:
        score += 1.5
    return score


def shortlist_assets(article_text: str, keywords: List[str], media: Dict[str, List[Dict]], links: List[Dict]) -> Dict:
    tokens = tokenize(article_text)

    acr_pairs = extract_acronym_pairs(article_text)
    asset_tokens = collect_asset_tokens(media, links)
    kset: Set[str] = set()
    for k in keywords:
        kset.update(keyword_variants_dynamic(k, tokens, asset_tokens, acr_pairs))
    logging.info(f"Dynamic keyword variants built | size={len(kset)}")

    # Score media
    media_scores: List[Tuple[Dict, float]] = []
    for img in media.get("images", []):
        score = _score_asset(img.get("title",""), img.get("description",""), img.get("tags",""), kset, tokens)
        media_scores.append(({"type":"image", **img}, score))
    for vid in media.get("videos", []):
        score = _score_asset(vid.get("title",""), vid.get("description",""), vid.get("tags",""), kset, tokens)
        media_scores.append(({"type":"video", **vid}, score))
    media_scores.sort(key=lambda x: x[1], reverse=True)

    # Score links with type authority
    type_weight = {
        "report": 2.2,
        "research": 2.0,
        "fact sheet": 1.8,
        "guide": 1.6,
        "policy": 1.5,
        "data": 1.4,
        "article": 1.2,
        "blog": 1.0,
        None: 1.0,
    }
    link_scores: List[Tuple[Dict, float]] = []
    for r in links:
        base = _score_asset(r.get("title",""), r.get("description",""), r.get("topic_tags",""), kset, tokens)
        w = type_weight.get((r.get("type") or "").strip().lower(), 1.0)
        link_scores.append((r, base * w))
    link_scores.sort(key=lambda x: x[1], reverse=True)

    # Split hero vs context candidates: favor images for hero
    top_media = [m for m, s in media_scores[:8]]
    hero_candidates = [m for m in top_media if m["type"] == "image"] or top_media
    context_candidates = top_media

    # Top links
    top_links = [l for l, s in link_scores[:8]]

    return {
        "hero": hero_candidates[:5],
        "context": context_candidates[:5],
        "links": top_links[:6],
    }