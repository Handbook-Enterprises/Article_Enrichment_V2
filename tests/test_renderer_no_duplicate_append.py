from shared.types import Place, MediaSelection, LinkSelection, Selection
from content_enrichment.renderer import render_enriched_markdown

def test_no_duplicate_link_append_when_link_present():
    original = (
        "# Title\n\n"
        "## Section\n\n"
        "1. First bullet item.\n"
        "2. Second bullet item.\n"
        "3. Direct air capture (DAC) explained with details.\n"
    )
    hero = MediaSelection(id=1, type="image", url="http://x/y.jpg", alt="Hero", place=Place(after_heading=True))
    ctx = MediaSelection(id=2, type="image", url="http://x/z.jpg", alt="Ctx", place=Place(section_heading="Section", after_heading=True))
    url = "http://x/r"
    anchor = "Direct air capture (DAC)"
    link = LinkSelection(id=3, url=url, anchor=anchor, keyword="capture", place=Place(section_heading="Section", paragraph_index=1, sentence_index=0, after_heading=True))
    sel = Selection(hero=hero, context_item=ctx, links=[link, link])
    enriched = render_enriched_markdown(original, sel, ["capture"], "")
    assert enriched.count(url) == 1
