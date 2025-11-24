from shared.types import Place, MediaSelection, LinkSelection, Selection
from content_enrichment.renderer import render_enriched_markdown

def test_anchor_matches_list_bold_with_nonbreaking_hyphen():
    original = (
        "# Title\n\n"
        "## Section\n\n"
        "1. **Pre\u2011combustion separation** – Fossil fuel is converted.\n"
    )
    hero = MediaSelection(id=1, type="image", url="http://x/y.jpg", alt="Hero", place=Place(after_heading=True))
    ctx = MediaSelection(id=2, type="image", url="http://x/z.jpg", alt="Ctx", place=Place(section_heading="Section", after_heading=True))
    url = "http://x/r"
    anchor = "Pre-combustion separation"
    link = LinkSelection(id=3, url=url, anchor=anchor, keyword="combustion", place=Place(section_heading="Section", paragraph_index=0, sentence_index=0, after_heading=True))
    sel = Selection(hero=hero, context_item=ctx, links=[link, link])
    enriched = render_enriched_markdown(original, sel, ["combustion"], "")
    assert "**[Pre\u2011combustion separation](http://x/r)**" in enriched
    assert enriched.count(url) == 1
