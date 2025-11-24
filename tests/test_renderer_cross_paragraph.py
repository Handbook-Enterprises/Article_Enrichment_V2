from shared.types import Place, MediaSelection, LinkSelection, Selection
from content_enrichment.renderer import render_enriched_markdown

def test_anchor_found_in_different_paragraph_within_section():
    original = (
        "# T\n\n"
        "## Section\n\n"
        "Intro text without the target phrase.\n\n"
        "Advances in membrane materials have cut capture energy penalties significantly.\n"
    )
    hero = MediaSelection(id=1, type="image", url="http://x/y.jpg", alt="Hero", place=Place(after_heading=True))
    ctx = MediaSelection(id=2, type="image", url="http://x/z.jpg", alt="Ctx", place=Place(section_heading="Section", after_heading=True))
    link = LinkSelection(
        id=3,
        url="http://x/r",
        anchor="capture energy penalties",
        keyword="penalties",
        place=Place(section_heading="Section", paragraph_index=0, sentence_index=0, after_heading=True),
    )
    sel = Selection(hero=hero, context_item=ctx, links=[link, link])
    enriched = render_enriched_markdown(original, sel, ["penalties"], "")
    assert "[capture energy penalties](http://x/r)" in enriched
