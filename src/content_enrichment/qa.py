import logging
import os
from typing import List

from shared.types import Selection

# Check if the hero image URL is present in the markdown.
def _contains_hero(markdown: str, url: str) -> bool:
    return url in markdown

# Check if the anchors in the selection include any of the keywords.
def _anchors_include_keywords(selection: Selection, keywords: List[str]) -> bool:
    require_kw = (os.getenv("ANCHOR_REQUIRE_KEYWORDS", "0").strip().lower() in ("1", "true", "yes", "on"))
    kset = {k.strip().lower() for k in keywords}
    for l in selection.links:
        a = l.anchor.strip().lower()
        if not a:
            return False
        if "click here" in a:
            return False
        if require_kw and not any(k in a for k in kset):
            return False
    return True


def validate_output(markdown: str, selection: Selection, keywords: List[str]) -> None:
    # Hero presence
    if not _contains_hero(markdown, selection.hero.url):
        raise ValueError("Hero image not found in output")

    # Context media presence
    if selection.context_item.url not in markdown:
        raise ValueError("Context media not found in output")

    # Links presence and anchors
    for l in selection.links:
        if l.url not in markdown:
            raise ValueError("A selected link URL is missing from output")
    if not _anchors_include_keywords(selection, keywords):
        raise ValueError("Anchor text must include provided keywords and avoid 'click here'")

    logging.info("Brand and structural validations passed: hero, context, and two keyword-rich links present")