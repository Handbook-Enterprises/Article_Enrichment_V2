import os
import logging
from pathlib import Path
from typing import Optional
from shared.types import Selection
from db.data_access import load_article, load_keywords, load_brand_rules, load_media_db, load_links_db
from content_enrichment.shortlist import build_article_profile, shortlist_assets
from content_enrichment.asset_validation import filter_candidates_by_availability
from ai.llm_select import select_assets_with_llm
from content_enrichment.renderer import render_enriched_markdown
from content_enrichment.qa import validate_output
from ai.qa_ai import verify_with_ai, QAResult
from flows.crewai_flow import record_step
from flows.crewai_agents import EnrichmentCrew

def enrich(article_path: str, keywords_path: str, out_path: Optional[str] = None, model: Optional[str] = None, offline: bool = False, qa_mode: str = "auto") -> str:
    root = Path(__file__).resolve().parents[1]
    media_db_path = root / "db" / "media.db"
    links_db_path = root / "db" / "links.db"
    brand_rules_path = root / "docs" / "brand_rules.txt"
    article_text = load_article(article_path)
    keywords = load_keywords(keywords_path)
    brand_rules_text = load_brand_rules(str(brand_rules_path))
    media = load_media_db(str(media_db_path))
    links = load_links_db(str(links_db_path))
    profile = build_article_profile(article_text)
    if os.getenv("USE_FLOW", "0").strip().lower() in ("1","true","yes","on"):
        record_step("profile", {"headings": profile.get("headings", [])})
    candidates = shortlist_assets(article_text, keywords, media, links)
    if os.getenv("USE_FLOW", "0").strip().lower() in ("1","true","yes","on"):
        record_step("shortlist", {"hero": len(candidates.get("hero", [])), "context": len(candidates.get("context", [])), "links": len(candidates.get("links", []))})
    candidates = filter_candidates_by_availability(candidates)
    
    # Initialize CrewAI agent wrapper (opt-in via USE_CREWAI_AGENTS)
    crew = EnrichmentCrew()
    def pre_validate(sel: Selection) -> tuple[bool, int]:
        score = 0
        generic = {"overview", "basics", "learn more", "click here"}
        for l in sel.links:
            a = (l.anchor or "").strip()
            toks = [t for t in a.split() if t.isalpha()]
            has_kw = any(k.lower() in a.lower() for k in keywords)
            length_ok = 8 <= len(a) <= 80
            tok_ok = len(toks) >= 2
            not_generic_only = not (a.lower() in generic)
            score += int(has_kw) + int(length_ok) + int(tok_ok) + int(not_generic_only)
        return (score >= 6, score)

    max_attempts = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    attempts: list[Selection] = []
    avoid_urls: set[str] = set()
    last_reasons: list[str] = []
    final_enriched: str = ""
    accepted = False

    for attempt in range(1, max_attempts + 1):
        logging.info(f"Selection attempt {attempt}/{max_attempts}")
        # Use CrewAI agent wrapper (falls back to direct call if USE_CREWAI_AGENTS=0)
        selection = crew.run_selection(
            article_text=article_text,
            profile=profile,
            keywords=keywords,
            candidates=candidates,
            brand_rules_text=brand_rules_text,
            model=model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            offline=offline or not (os.getenv("OPENROUTER_API_KEY") or "").strip(),
            previous_selection=(attempts[-1] if attempts else None),
            reject_reasons=last_reasons or None,
            avoid_urls=list(avoid_urls) if avoid_urls else None,
        )

        ok, qscore = pre_validate(selection)
        logging.info(f"Pre-validation | score={qscore} | ok={'yes' if ok else 'no'}")
        enriched = render_enriched_markdown(
            original_markdown=article_text,
            selection=selection,
            keywords=keywords,
            brand_rules_text=brand_rules_text,
        )
        if os.getenv("USE_FLOW", "0").strip().lower() in ("1","true","yes","on"):
            record_step("render", {"hero": selection.hero.url, "context": selection.context_item.url})
            record_step(f"attempt_{attempt}", {"hero": selection.hero.url, "context": selection.context_item.url, "links": [l.url for l in selection.links], "pre_score": qscore})

        logging.info(f"QA mode: {qa_mode}")
        if qa_mode == "fallback":
            validate_output(enriched, selection, keywords)
            logging.info("Fallback QA passed")
            final_enriched = enriched
            accepted = True
            break

        try:
            # Use CrewAI agent wrapper (falls back to direct call if USE_CREWAI_AGENTS=0)
            res: QAResult = crew.run_qa(enriched, selection, keywords, brand_rules_text)
            passed = bool(res.accepted) or (res.rating is not None and res.rating >= res.threshold)
            logging.info(
                f"AI QA result | accepted={res.accepted} | rating={res.rating} | threshold={res.threshold} | reasons={'; '.join(res.reasons) if res.reasons else ''}"
            )
            if passed and ok:
                logging.info("AI QA passed")
                final_enriched = enriched
                accepted = True
                if os.getenv("USE_FLOW", "0").strip().lower() in ("1","true","yes","on"):
                    record_step(f"attempt_{attempt}_accepted", {"rating": res.rating, "reasons": res.reasons})
                break
            else:
                last_reasons = (res.reasons or []) + ([] if ok else ["pre-validation quality below threshold"])
                avoid_urls.update({selection.hero.url, selection.context_item.url, *(l.url for l in selection.links)})
                attempts.append(selection)
                logging.info("Retrying with diversity constraints and QA feedback")
        except Exception as e:
            logging.warning(f"AI QA unavailable or error ({e}); {'retrying' if qa_mode!='fallback' else 'using fallback'}")
            if qa_mode == "auto":
                try:
                    validate_output(enriched, selection, keywords)
                    logging.info("Fallback QA passed")
                    final_enriched = enriched
                    accepted = True
                    break
                except Exception as fe:
                    logging.error(f"Fallback QA failed: {fe}")
                    last_reasons = ["ai qa error and fallback failed"]
                    avoid_urls.update({selection.hero.url, selection.context_item.url, *(l.url for l in selection.links)})
                    attempts.append(selection)
            else:
                last_reasons = ["ai qa error"]
                avoid_urls.update({selection.hero.url, selection.context_item.url, *(l.url for l in selection.links)})
                attempts.append(selection)

    if attempts:
        all_urls = []
        for s in attempts:
            all_urls.extend([s.hero.url, s.context_item.url, *(l.url for l in s.links)])
        repeats = len(all_urls) - len(set(all_urls))
        ratio = (repeats / max(1, len(all_urls))) * 100.0
        logging.info(f"Diversity metric | repeat_selection_ratio={ratio:.2f}% | attempts={len(attempts)}")

    if not accepted:
        raise ValueError("Enrichment not accepted after retry attempts")
    default_out = root / "outputs" / f"enriched_{Path(article_path).name}"
    final = out_path or str(default_out)
    Path(final).write_text(final_enriched, encoding="utf-8")
    logging.info(f"Output written: {final}")
    return final
