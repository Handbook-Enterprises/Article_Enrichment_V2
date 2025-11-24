import os
from typing import List, Optional
from pydantic import BaseModel, Field
from shared.types import Selection
from instructor import from_openai
from openai import OpenAI

class QAResult(BaseModel):
    accepted: Optional[bool] = None
    rating: Optional[int] = None
    reasons: List[str] = []
    threshold: int = Field(default=int(os.getenv("QA_THRESHOLD", "7")))

def verify_with_ai(markdown: str, selection: Selection, keywords: List[str], brand_rules_text: str) -> QAResult:
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    client = from_openai(OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key))
    prompt = {
        "article": markdown,
        "selection": {
            "hero": {"url": selection.hero.url, "alt": selection.hero.alt, "type": selection.hero.type},
            "context": {"url": selection.context_item.url, "alt": selection.context_item.alt, "type": selection.context_item.type, "section": selection.context_item.place.section_heading},
            "links": [{"url": l.url, "anchor": l.anchor, "keyword": l.keyword, "section": l.place.section_heading} for l in selection.links],
        },
        "keywords": keywords,
        "brand_rules": brand_rules_text,
        "criteria": [
            "Exactly one hero image after H1",
            "One in-context image or video placed under a relevant section",
            "Two contextual hyperlinks integrated inline with descriptive anchors including provided keywords",
            "Alt text descriptive and <=125 characters; no 'Image of' or 'Picture of'",
            "No em dashes in generated anchors",
        ],
    }
    res = client.chat.completions.create(model=model, messages=[{"role": "system", "content": "Return only the structured object"}, {"role": "user", "content": str(prompt)}], response_model=QAResult, temperature=0)
    return res
