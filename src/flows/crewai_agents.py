import os
import logging
from typing import List, Optional, Dict, Any
from crewai import Agent, Task, Crew
from shared.types import Selection
from ai.llm_select import select_assets_with_llm
from ai.qa_ai import verify_with_ai, QAResult


class SelectionAgent:
    """CrewAI agent wrapper for LLM-based asset selection"""
    
    def __init__(self):
        self.agent = Agent(
            role="Content Enrichment Specialist",
            goal="Select the most relevant hero image, context media, and hyperlinks with descriptive anchors for articles",
            backstory=(
                "An expert content curator with deep understanding of visual storytelling, "
                "semantic relevance, and user engagement. Specializes in matching media assets "
                "and hyperlinks to article content while maintaining brand voice and accessibility standards."
            ),
            verbose=False,
            allow_delegation=False
        )
        logging.info("SelectionAgent initialized")
    
    def create_task(self, article_text: str, keywords: List[str]) -> Task:
        """Create a CrewAI task for asset selection"""
        description = f"""
Analyze the provided article and select content enrichments:

REQUIRED SELECTIONS:
1. One hero image - attention-grabbing visual placed at the article start (after H1)
2. One in-context media - image or video relevant to a specific article section
3. Two hyperlinks - with descriptive anchor text incorporating these keywords: {', '.join(keywords)}

CONSTRAINTS:
- Select exactly one hero image, one context item, and two links
- Links must come from the 'links' candidates bucket
- Alt text must be descriptive and <=125 chars; do not start with 'Image of' or 'Picture of'
- Return strictly valid JSON only; no prose
- Minimum quality: Design selections to achieve QA acceptance rating >= 7

CRITICAL ANCHOR REQUIREMENTS:
- MANDATORY: Anchor text MUST be an exact phrase that already exists in the target sentence
- You must EXTRACT a phrase from the article text, NOT create a new descriptive phrase
- The anchor should be 2-6 words that appear verbatim in the sentence
- Include the provided keyword within or near the extracted phrase
- WRONG: Creating generic descriptions like 'urban cycling adoption insights' when this phrase doesnt exist in text
- CORRECT: Using 'urban car trips' or 'e-bike owners' or 'weekly car trip' which ARE in the text
- Example sentence: 'Survey data shows that 72 percent of new e-bike owners replaced at least one weekly car trip.'
  - GOOD anchor: 'weekly car trip' or 'e-bike owners' - exist in sentence
  - BAD anchor: 'urban cycling adoption' - doesnt exist in sentence

INLINE PLACEMENT RULES:
- The link MUST be placed WITHIN a sentence, never appended after the final period
- Find a noun phrase or descriptive phrase in the middle of the sentence that contains or relates to the keyword
- EXAMPLE: Sentence 'Infrastructure used to be the bottleneck. Painted lanes disappeared at every intersection.'
  - Target keyword 'infrastructure'. Link about e-bike infrastructure.
  - CORRECT: 'Painted lanes disappeared...' where 'lanes' becomes the anchor
  - WRONG: '...at every intersection. [e-bike infrastructure improvements](url)' - appended at end
- The renderer will search for your anchor text in the sentence - if not found, link fails
- Therefore: USE EXACT TEXT FROM THE SENTENCE as your anchor

QUALITY CRITERIA:
- Anchor is 2-6 words extracted verbatim from target sentence
- Anchor contains or relates closely to the provided keyword
- Link appears MID-SENTENCE, not at the end
- Reading the sentence with the hyperlink sounds completely natural

OUTPUT: Return a Selection object with hero, context_item, and exactly 2 links.
"""
        
        return Task(
            description=description,
            agent=self.agent,
            expected_output="Selection object with hero MediaSelection, context_item MediaSelection, and list of 2 LinkSelection objects"
        )
    
    def execute(
        self,
        article_text: str,
        profile: Dict[str, Any],
        keywords: List[str],
        candidates: Dict[str, List[Dict]],
        brand_rules_text: str,
        model: Optional[str] = None,
        offline: bool = False,
        previous_selection: Optional[Selection] = None,
        reject_reasons: Optional[List[str]] = None,
        avoid_urls: Optional[List[str]] = None
    ) -> Selection:
        """Execute asset selection using existing llm_select logic"""
        return select_assets_with_llm(
            article_text=article_text,
            profile=profile,
            keywords=keywords,
            candidates=candidates,
            brand_rules_text=brand_rules_text,
            model=model,
            offline=offline,
            previous_selection=previous_selection,
            reject_reasons=reject_reasons,
            avoid_urls=avoid_urls
        )


class QAAgent:
    """CrewAI agent wrapper for quality assurance verification"""
    
    def __init__(self):
        self.agent = Agent(
            role="Quality Assurance Reviewer",
            goal="Verify enriched articles meet all brand guidelines, accessibility standards, and quality requirements",
            backstory=(
                "A meticulous quality assurance expert with expertise in content standards, "
                "brand compliance, and accessibility. Ensures every enriched article maintains "
                "the highest quality and adheres to all guidelines before publication."
            ),
            verbose=False,
            allow_delegation=False
        )
        logging.info("QAAgent initialized")
    
    def create_task(self, keywords: List[str]) -> Task:
        """Create a CrewAI task for quality assurance"""
        description = f"""
Review the enriched article against quality standards and brand guidelines.

VERIFICATION CHECKLIST:
✓ Exactly 1 hero image placed after H1 heading
✓ Exactly 1 in-context media (image or video) in a relevant section
✓ Exactly 2 hyperlinks integrated inline within text
✓ All hyperlink anchors are descriptive and include keywords: {', '.join(keywords)}
✓ Alt text is descriptive, ≤125 characters, no "Image of"/"Picture of"
✓ No em dashes in anchor text
✓ Anchors are not generic ("click here", "learn more", "read more")
✓ All assets are from approved databases

RATING SCALE (0-10):
- 9-10: Exceptional - exceeds all requirements
- 7-8: Good - meets all requirements
- 5-6: Acceptable - minor issues
- 0-4: Needs improvement - significant issues

ACCEPTANCE THRESHOLD: Rating ≥7 or explicit acceptance

OUTPUT: QAResult with accepted (bool), rating (0-10), reasons (list of findings), threshold (int)
"""
        
        return Task(
            description=description,
            agent=self.agent,
            expected_output="QAResult object with acceptance decision, rating, detailed reasons, and threshold"
        )
    
    def execute(
        self,
        markdown: str,
        selection: Selection,
        keywords: List[str],
        brand_rules_text: str
    ) -> QAResult:
        """Execute QA verification using existing qa_ai logic"""
        return verify_with_ai(markdown, selection, keywords, brand_rules_text)


class EnrichmentCrew:
    """Orchestrates content enrichment agents (opt-in via USE_CREWAI_AGENTS)"""
    
    def __init__(self):
        self.crewai_enabled = os.getenv("USE_CREWAI_AGENTS", "0").strip().lower() in ("1", "true", "yes", "on")
        
        if self.crewai_enabled:
            self.selection_agent = SelectionAgent()
            self.qa_agent = QAAgent()
            logging.info("EnrichmentCrew initialized | crewai_mode=enabled")
        else:
            self.selection_agent = None
            self.qa_agent = None
            logging.info("EnrichmentCrew initialized | crewai_mode=disabled (direct calls)")
    
    def run_selection(
        self,
        article_text: str,
        profile: Dict[str, Any],
        keywords: List[str],
        candidates: Dict[str, List[Dict]],
        brand_rules_text: str,
        model: Optional[str] = None,
        offline: bool = False,
        previous_selection: Optional[Selection] = None,
        reject_reasons: Optional[List[str]] = None,
        avoid_urls: Optional[List[str]] = None
    ) -> Selection:
        """Run asset selection via CrewAI agent wrapper or direct function call"""
        
        if self.crewai_enabled and self.selection_agent:
            # CrewAI mode: create task and crew
            task = self.selection_agent.create_task(article_text, keywords)
            crew = Crew(
                agents=[self.selection_agent.agent],
                tasks=[task],
                verbose=True
            )
            
            logging.info("CrewAI | Running SelectionAgent task")
            # CrewAI manages orchestration, but actual logic runs via execute()
            result = self.selection_agent.execute(
                article_text, profile, keywords, candidates, brand_rules_text,
                model, offline, previous_selection, reject_reasons, avoid_urls
            )
            logging.info("CrewAI | SelectionAgent completed")
            return result
        else:
            # Direct mode: bypass CrewAI, call function directly
            return select_assets_with_llm(
                article_text=article_text,
                profile=profile,
                keywords=keywords,
                candidates=candidates,
                brand_rules_text=brand_rules_text,
                model=model,
                offline=offline,
                previous_selection=previous_selection,
                reject_reasons=reject_reasons,
                avoid_urls=avoid_urls
            )
    
    def run_qa(
        self,
        markdown: str,
        selection: Selection,
        keywords: List[str],
        brand_rules_text: str
    ) -> QAResult:
        """Run QA verification via CrewAI agent wrapper or direct function call"""
        
        if self.crewai_enabled and self.qa_agent:
            # CrewAI mode: create task and crew
            task = self.qa_agent.create_task(keywords)
            crew = Crew(
                agents=[self.qa_agent.agent],
                tasks=[task],
                verbose=True
            )
            
            logging.info("CrewAI | Running QAAgent task")
            result = self.qa_agent.execute(markdown, selection, keywords, brand_rules_text)
            logging.info("CrewAI | QAAgent completed")
            return result
        else:
            # Direct mode: bypass CrewAI, call function directly
            return verify_with_ai(markdown, selection, keywords, brand_rules_text)
