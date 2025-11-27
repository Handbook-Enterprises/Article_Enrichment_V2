import os
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from shared.types import Selection
from instructor import from_openai
from openai import OpenAI

class QAResult(BaseModel):
    accepted: Optional[bool] = None
    rating: Optional[int] = None
    reasons: List[str] = []
    threshold: int = 7

def verify_with_ai(markdown: str, selection: Selection, keywords: List[str], brand_rules_text: str) -> tuple[QAResult, float]:
    """
    Verify enriched article quality using AI
    Returns: (QAResult, estimated_cost)
    """
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
    
    completion = client.chat.completions.create(
        model=model, 
        messages=[
            {"role": "system", "content": "Return only the structured object"}, 
            {"role": "user", "content": str(prompt)}
        ], 
        response_model=QAResult, 
        temperature=0
    )
    
    completion.threshold = int(os.getenv("QA_THRESHOLD", "7"))
    
    estimated_cost = 0.0
    if hasattr(completion, '_raw_response') and hasattr(completion._raw_response, 'usage'):
        usage = completion._raw_response.usage
        prompt_tokens = usage.prompt_tokens
        completion_tokens = usage.completion_tokens
        total_tokens = usage.total_tokens
        
        estimated_cost = (prompt_tokens / 1_000_000) * 0.15 + (completion_tokens / 1_000_000) * 0.60
        
        logging.info(
            f"QA LLM cost tracking | model={model} | "
            f"prompt_tokens={prompt_tokens} | completion_tokens={completion_tokens} | "
            f"total_tokens={total_tokens} | estimated_cost=${estimated_cost:.6f}"
        )
    
    return completion, estimated_cost
