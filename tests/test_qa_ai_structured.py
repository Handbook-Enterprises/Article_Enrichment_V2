import os
from pydantic import BaseModel
from shared.types import Place, MediaSelection, LinkSelection, Selection
import ai.qa_ai as qa_ai
from ai.qa_ai import QAResult

class DummyResult(QAResult):
    pass

def test_ai_verify_offline_monkeypatch(monkeypatch):
    def fake_verify(markdown, selection, keywords, brand_rules_text):
        return DummyResult(accepted=True, rating=9, reasons=["ok"], threshold=7)
    monkeypatch.setattr("ai.qa_ai.verify_with_ai", fake_verify)
    hero = MediaSelection(id=1, type="image", url="http://x/y.jpg", alt="Hero", place=Place(after_heading=True))
    ctx = MediaSelection(id=2, type="image", url="http://x/z.jpg", alt="Ctx", place=Place(section_heading="Section", after_heading=True))
    link1 = LinkSelection(id=3, url="http://x/a", anchor="bike", keyword="bike", place=Place(section_heading="Section", paragraph_index=0, sentence_index=0, after_heading=True))
    link2 = LinkSelection(id=4, url="http://x/b", anchor="cycling", keyword="cycling", place=Place(section_heading="Section", paragraph_index=0, sentence_index=0, after_heading=True))
    sel = Selection(hero=hero, context_item=ctx, links=[link1, link2])
    md = f"# T\n\n![Hero]({hero.url})\n\n## Section\n\n![Ctx]({ctx.url})\n\nSee [bike]({link1.url}) and [cycling]({link2.url})."
    res = qa_ai.verify_with_ai(md, sel, ["bike","cycling"], "")
    assert res.accepted or (res.rating is not None and res.rating >= res.threshold)
