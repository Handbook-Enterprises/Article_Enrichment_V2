import json
import os
from typing import Dict, List
import logging

import httpx

from shared.types import Selection, MediaSelection, LinkSelection, Place

def _sanitize_selection(selection: Selection, keywords: List[str]) -> Selection:
    """Ensure anchors include provided keywords and avoid banned phrases.
    Only replace when the anchor is banned/empty.
    """
    klist = [k.strip() for k in keywords if k and k.strip()]
    if not klist:
        return selection

    new_links: List[LinkSelection] = []
    sanitized = 0
    for i, l in enumerate(selection.links):
        anchor = (l.anchor or "").strip()
        al = anchor.lower()
        kw = (l.keyword or klist[i % len(klist)]).strip()

        banned = (not anchor) or ("click here" in al)
        has_kw = any(k.lower() in al for k in klist)

        if banned:
            # Replace entirely with safe, keyword-rich anchor
            safe_anchor = f"{kw} overview" if len(kw) <= 40 else kw[:60]
            new_links.append(
                LinkSelection(id=l.id, url=l.url, anchor=safe_anchor, keyword=kw, place=l.place)
            )
            sanitized += 1
        elif not has_kw:
            appended = f"{anchor} ({kw})"
            final_anchor = appended if len(appended) <= 80 else f"{anchor} ({kw})"
            new_links.append(
                LinkSelection(id=l.id, url=l.url, anchor=final_anchor, keyword=kw, place=l.place)
            )
            sanitized += 1
        else:
            #  keep as-is 
            new_links.append(
                LinkSelection(id=l.id, url=l.url, anchor=anchor, keyword=kw, place=l.place)
            )
    selection.links = new_links
    if sanitized:
        logging.info(f"Anchor sanitization applied to {sanitized} link(s)")
    return selection


def _compact_asset(asset: Dict) -> Dict:
    return {
        "id": asset.get("id"),
        "type": asset.get("type", "resource"),
        "url": asset.get("url"),
        "title": asset.get("title"),
        "description": asset.get("description"),
        "tags": asset.get("tags") or asset.get("topic_tags"),
        "extra_type": asset.get("type"),
    }


def _build_prompt(_article_text: str, profile: Dict, keywords: List[str], candidates: Dict, brand_rules_text: str, previous_selection: Selection | None = None, reject_reasons: List[str] | None = None, avoid_urls: List[str] | None = None) -> str:
    # Prompt mode toggle via env: both | paragraphs | full
    prompt_mode = os.getenv("PROMPT_MODE", "both").strip().lower()

    # Build sections with paragraphs from the full article content
    def paragraphs_from_lines(lines: List[str]) -> List[str]:
        paras: List[str] = []
        i = 0
        while i < len(lines):
            while i < len(lines) and (lines[i] or "").strip() == "":
                i += 1
            if i >= len(lines):
                break
            j = i
            while j < len(lines) and (lines[j] or "").strip() != "":
                j += 1
            paras.append(" ".join(lines[i:j]).strip())
            i = j + 1
        return paras

    sections_payload: List[Dict] = []
    for s in profile.get("sections", [])[:6]:
        sections_payload.append({
            "heading": s["heading"],
            "paragraphs": paragraphs_from_lines(s.get("content", [])),
        })
    base_payload = {
        "keywords": keywords,
        "brand_rules": brand_rules_text,
        "candidates": {
            "hero": [_compact_asset(a) for a in candidates.get("hero", [])],
            "context": [_compact_asset(a) for a in candidates.get("context", [])],
            "links": [_compact_asset(a) for a in candidates.get("links", [])],
        },
        "output_schema": {
            "hero": {"id": "int", "type": "image", "url": "str", "alt": "str", "place": {"after_heading": "h1"}},
            "context_item": {"id": "int", "type": "image|video", "url": "str", "alt": "str", "place": {"section_heading": "str", "after_heading": True}},
            "links": [{"id": "int", "url": "str", "anchor": "str", "keyword": "str", "place": {"section_heading": "str", "paragraph_index": "int", "sentence_index": "int"}}],
        },
        "constraints": [
            "Select exactly one hero image at the beginning of the article",
            "Select exactly one in-context item (image or video)",
            "Select exactly two links; anchor text must include provided keywords and be descriptive",
            "Links must come from the 'links' candidates bucket; do not reuse hero/context URLs as links",
            "Alt text must be descriptive and <=125 chars; do not start with 'Image of' or 'Picture of'",
            "Use only URLs from candidates; do not modify URLs",
            "Indices are zero-based. Paragraphs are contiguous non-empty lines in the target section. Sentence index is the position within the chosen paragraph when splitting on '.', '!', or '?'",
            "Return strictly valid JSON only; no prose",
            "Minimum quality: Design selections to achieve QA acceptance rating >= 7",
            "Diversity: Avoid repeating previous selections (hero/context/link URLs, anchors, and locations)",
        ],
        "CRITICAL_anchor_requirements": [
            "MANDATORY: Anchor text MUST be an exact phrase that already exists in the target sentence",
            "You must EXTRACT a phrase from the article text, NOT create a new descriptive phrase",
            "The anchor should be 2-6 words that appear verbatim in the sentence",
            "Include the provided keyword within or near the extracted phrase",
            "WRONG: Creating generic descriptions like 'urban cycling adoption insights' when this phrase doesnt exist in text",
            "CORRECT: Using 'urban car trips' or 'e-bike owners' or 'weekly car trip' which ARE in the text",
            "Example sentence: 'Survey data shows that 72 percent of new e-bike owners replaced at least one weekly car trip.'",
            "GOOD anchor: 'weekly car trip' or 'e-bike owners' or 'new e-bike owners' - all exist in sentence",
            "BAD anchor: 'urban cycling adoption' - doesnt exist in sentence, sounds like a title",
            "If the keyword is 'urban cycling', find a sentence with 'urban' or 'cycling' or 'city' or 'commuters' and extract that exact phrase",
        ],
        "inline_placement_rules": [
            "The link MUST be placed WITHIN a sentence, never appended after the final period",
            "Find a noun phrase or descriptive phrase in the middle of the sentence that contains or relates to the keyword",
            "EXAMPLE 1: Sentence 'Infrastructure used to be the bottleneck. Painted lanes disappeared at every intersection.'",
            "  Target keyword 'infrastructure'. Link about e-bike infrastructure.",
            "  CORRECT placement: 'Painted lanes disappeared...' where 'lanes' becomes the anchor - its inline and relates to infrastructure",
            "  WRONG: '...at every intersection. [e-bike infrastructure improvements](url)' - appended at end",
            "EXAMPLE 2: Sentence 'Municipal governments have accelerated investment in protected cycle tracks.'",
            "  Target keyword 'infrastructure'. Link about cycle infrastructure.",
            "  CORRECT: 'investment in protected cycle tracks' where 'protected cycle tracks' is the anchor",
            "  WRONG: '...cycle tracks. [infrastructure guide](url)' - citation style",
            "The renderer will search for your anchor text in the sentence - if not found, link fails",
            "Therefore: USE EXACT TEXT FROM THE SENTENCE as your anchor",
        ],
        "placement_rules": [
            "Whole-word insertion only",
            "If word has possessive, place anchor after possessive",
            "Never split numbers or decimals",
        ],
        "quality_criteria": [
            "Anchor is 2-6 words extracted verbatim from target sentence",
            "Anchor contains or relates closely to the provided keyword",
            "Link appears MID-SENTENCE, not at the end",
            "Reading the sentence with the hyperlink sounds completely natural",
        ],
    }

    if previous_selection:
        base_payload["previous_selection"] = {
            "hero": {"url": previous_selection.hero.url, "alt": previous_selection.hero.alt},
            "context": {"url": previous_selection.context_item.url, "alt": previous_selection.context_item.alt, "section": previous_selection.context_item.place.section_heading},
            "links": [{"url": l.url, "anchor": l.anchor, "keyword": l.keyword, "section": l.place.section_heading} for l in previous_selection.links],
        }
    if reject_reasons:
        base_payload["reject_reasons"] = reject_reasons
    if avoid_urls:
        base_payload["avoid_urls"] = avoid_urls

    if prompt_mode == "paragraphs":
        base_payload["article_sections"] = sections_payload
    elif prompt_mode == "full":
        base_payload["article_text"] = _article_text
        base_payload["allowed_headings"] = [s.get("heading") for s in profile.get("sections", [])[:6]]
    else:  # both (default)
        base_payload["article_text"] = _article_text
        base_payload["article_sections"] = sections_payload

    return json.dumps(base_payload, ensure_ascii=False)


def _fallback_selection(_article_text: str, profile: Dict, keywords: List[str], candidates: Dict) -> Selection:
    hero_bucket = candidates.get("hero", [])
    context_bucket = candidates.get("context", [])
    link_bucket = candidates.get("links", [])
    if not hero_bucket:
        raise ValueError("No hero candidates available")
    hero = hero_bucket[0]
    context = context_bucket[1] if len(context_bucket) > 1 else (context_bucket[0] if context_bucket else hero)
    links = link_bucket[:2] if len(link_bucket) >= 2 else link_bucket

    # heading for context heuristically
    headings = [h.lower() for h in profile.get("headings", [])]
    target = None
    hints = [
        "infrastructure",
        "storage",
        "how co2 is captured",
        "moving the molecule",
        "why commuters are switching",
    ]
    for h in headings:
        if any(ht in h for ht in hints):
            target = h
            break
    target = target or (headings[0] if headings else None)

    hero_sel = MediaSelection(
        id=hero["id"],
        type="image",
        url=hero["url"],
        alt=(hero.get("description") or hero.get("title") or "Hero image").strip()[:120],
        place=Place(section_heading=None, paragraph_index=None, sentence_index=None, after_heading=True),
    )
    context_sel = MediaSelection(
        id=context["id"],
        type=context.get("type", "image"),
        url=context["url"],
        alt=(context.get("description") or context.get("title") or "Context media").strip()[:120],
        place=Place(section_heading=target, paragraph_index=None, sentence_index=None, after_heading=True),
    )

    def make_anchor(link: Dict, keyword: str) -> str:
        base = (link.get("title") or link.get("description") or "overview").lower()
        # Build a descriptive anchor that contains keyword
        if keyword.lower() in base:
            return base[:60]
        return f"{keyword} basics" if len(keyword) < 40 else keyword[:60]

    link_selections = []
    for i, link in enumerate(links):
        kw = keywords[i % len(keywords)]
        anchor = make_anchor(link, kw)
        link_selections.append(
            LinkSelection(
                id=link["id"],
                url=link["url"],
                anchor=anchor,
                keyword=kw,
                place=Place(section_heading=target, paragraph_index=0, sentence_index=0, after_heading=True),
            )
        )

    return Selection(hero=hero_sel, context_item=context_sel, links=link_selections)


def select_assets_with_llm(article_text: str, profile: Dict, keywords: List[str], candidates: Dict, brand_rules_text: str, model: str, offline: bool, previous_selection: Selection | None = None, reject_reasons: List[str] | None = None, avoid_urls: List[str] | None = None) -> tuple[Selection, float]:
    if offline:
        logging.info("LLM disabled or API key missing; using fallback deterministic selection")
        return _fallback_selection(article_text, profile, keywords, candidates), 0.0

    # Resolve effective model and debug flag from environment
    effective_model = model or os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
    debug_flag = (os.getenv("LLM_DEBUG", "0").strip().lower() in ("1", "true", "yes", "on"))

    prompt = _build_prompt(article_text, profile, keywords, candidates, brand_rules_text, previous_selection=previous_selection, reject_reasons=reject_reasons, avoid_urls=avoid_urls)

    api_key = os.getenv("OPENROUTER_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": effective_model,
        "messages": [
            {"role": "system", "content": "You are a precise content selection assistant. Return only valid JSON per the provided schema."},
            {"role": "user", "content": prompt},
        ],
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
    }

    estimated_cost = 0.0
    try:
        logging.info(f"LLM config | model={effective_model} | debug={'on' if debug_flag else 'off'} | prompt_mode={os.getenv('PROMPT_MODE','both').strip().lower()}")
        # Show exactly what we're sending (not auth) when debug is on
        if debug_flag:
            logging.info("LLM request body (no auth):\n%s", json.dumps(body, ensure_ascii=False, indent=2))
            logging.info("LLM prompt payload (user content):\n%s", prompt)
        resp = httpx.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body, timeout=int(os.getenv("LLM_TIMEOUT", "60")))
        resp.raise_for_status()
        
        response_json = resp.json()
        if 'usage' in response_json:
            usage = response_json['usage']
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            total_tokens = usage.get('total_tokens', 0)
            
            estimated_cost = (prompt_tokens / 1_000_000) * 0.15 + (completion_tokens / 1_000_000) * 0.60
            
            logging.info(
                f"LLM cost tracking | model={effective_model} | "
                f"prompt_tokens={prompt_tokens} | completion_tokens={completion_tokens} | "
                f"total_tokens={total_tokens} | estimated_cost=${estimated_cost:.6f}"
            )
        
        logging.info("LLM response received; parsing JSON")
        content = response_json["choices"][0]["message"]["content"].strip()
        if debug_flag:
            logging.info("LLM raw content (as received):\n%s", content)
        data = json.loads(content)
     
        if debug_flag:
            logging.info("LLM JSON parsed (pretty):\n%s", json.dumps(data, ensure_ascii=False, indent=2))
        # Map JSON to pydantic models
        hero = data["hero"]
        context_item = data["context_item"]
        links = data["links"]
        selection = Selection(
            hero=MediaSelection(
                id=int(hero["id"]), type=hero.get("type","image"), url=hero["url"], alt=hero["alt"], place=Place(after_heading=True)
            ),
            context_item=MediaSelection(
                id=int(context_item["id"]), type=context_item.get("type","image"), url=context_item["url"], alt=context_item["alt"],
                place=Place(section_heading=context_item.get("place",{}).get("section_heading"), after_heading=True)
            ),
            links=[
                LinkSelection(
                    id=int(l["id"]), url=l["url"], anchor=l["anchor"], keyword=l["keyword"],
                    place=Place(section_heading=l.get("place",{}).get("section_heading"), paragraph_index=l.get("place",{}).get("paragraph_index"), sentence_index=l.get("place",{}).get("sentence_index"), after_heading=True)
                ) for l in links
            ]
        )
        # Optional anchor sanitization controlled via .env ANCHOR_SANITIZE
        anchor_sanitize = (os.getenv("ANCHOR_SANITIZE", "0").strip().lower() in ("1", "true", "yes", "on"))
        if anchor_sanitize:
            selection = _sanitize_selection(selection, keywords)
        return selection, estimated_cost
    except Exception as e:
        # If parsing failed, show the raw content to aid debugging (debug only)
        try:
            if debug_flag:
                raw = resp.json()["choices"][0]["message"]["content"].strip() if 'resp' in locals() else "<no content>"
                logging.error("LLM selection failed: %s\nRaw content was:\n%s", e, raw)
            else:
                logging.error("LLM selection failed: %s", e)
        except Exception:
            logging.error("LLM selection failed: %s (raw content unavailable)", e)
        logging.warning("Falling back to deterministic selection")
        return _fallback_selection(article_text, profile, keywords, candidates), 0.0
