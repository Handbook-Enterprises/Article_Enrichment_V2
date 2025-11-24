from shared.types import Place, MediaSelection, LinkSelection, Selection
from content_enrichment.qa import validate_output

def test_validate_output_passes():
    hero = MediaSelection(id=1, type="image", url="http://x/y.jpg", alt="Hero", place=Place(after_heading=True))
    ctx = MediaSelection(id=2, type="image", url="http://x/z.jpg", alt="Ctx", place=Place(section_heading="Section", after_heading=True))
    link1 = LinkSelection(id=3, url="http://x/a", anchor="bike commuting basics", keyword="bike", place=Place(section_heading="Section", paragraph_index=0, sentence_index=0, after_heading=True))
    link2 = LinkSelection(id=4, url="http://x/b", anchor="cycling adoption overview", keyword="cycling", place=Place(section_heading="Section", paragraph_index=0, sentence_index=0, after_heading=True))
    sel = Selection(hero=hero, context_item=ctx, links=[link1, link2])
    md = f"# Title\n\n![Hero]({hero.url})\n\n## Section\n\nParagraph.\n\n![Ctx]({ctx.url})\n\nSee [bike commuting basics]({link1.url}) and [cycling adoption overview]({link2.url})."
    validate_output(md, sel, ["bike", "cycling"])
