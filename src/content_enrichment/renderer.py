import re
import logging
from typing import List, Tuple, Dict, Set
from shared.types import Selection

SECTION_RE = re.compile(r"^(#{1,6})\s+(.*)$")

def _strip_markdown_formatting(text: str) -> str:
    s = re.sub(r"!\[([^\]]*)\]\(([^)]*)\)", r"\1", text or "")
    s = re.sub(r"\[([^\]]+)\]\(([^)]*)\)", r"\1", s)
    s = re.sub(r"`+", "", s)
    s = re.sub(r"\*\*|__|\*|_", "", s)
    s = re.sub(r"^\s*#{1,6}\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*>\s*", "", s, flags=re.MULTILINE)
    return s

def _normalize_url(u: str) -> str:
    return re.sub(r"\s+", "", (u or ""))

def _extract_urls(text: str) -> Set[str]:
    urls = set()
    for m in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text, flags=re.S):
        urls.add(_normalize_url(m.group(1)))
    return urls

def _find_h1_index(lines: List[str]) -> int:
    for i, line in enumerate(lines):
        if line.startswith("# "):
            return i
    return -1

def _find_heading_index(lines: List[str], heading_text: str) -> int:
    if not heading_text:
        return -1
    target = heading_text.strip().lower()
    for i, line in enumerate(lines):
        m = SECTION_RE.match(line)
        if m and m.group(2).strip().lower() == target:
            return i
    # fuzzy contains
    for i, line in enumerate(lines):
        m = SECTION_RE.match(line)
        if m and target in m.group(2).strip().lower():
            return i
    return -1


def _insert_after(lines: List[str], index: int, block: str) -> List[str]:
    if index < 0:
        return [block] + lines
    return lines[: index + 1] + ["", block, ""] + lines[index + 1 :]


def _make_image_markdown(alt: str, url: str) -> str:
    return f"![{alt}]({url})"


def _make_video_block(title_or_alt: str, url: str) -> str:
    text = title_or_alt.strip() or "Watch"
    if text.endswith("."):
        text = text[:-1].strip()
    return f"▶ [{text}]({url})"

# Hero after H1 (beginning of article)
def render_enriched_markdown(original_markdown: str, selection: Selection, keywords: List[str], brand_rules_text: str) -> str:
    lines = original_markdown.splitlines()


    h1_idx = _find_h1_index(lines)
    hero_block = _make_image_markdown(selection.hero.alt, selection.hero.url)
    lines = _insert_after(lines, h1_idx, hero_block)
    logging.info(f"Renderer | hero inserted after H1 index={h1_idx}")

    # In-context media
    ctx_idx = _find_heading_index(lines, selection.context_item.place.section_heading)
    if selection.context_item.type == "image":
        ctx_block = _make_image_markdown(selection.context_item.alt, selection.context_item.url)
    else:
        ctx_block = _make_video_block(selection.context_item.alt, selection.context_item.url)
    lines = _insert_after(lines, ctx_idx, ctx_block)
    logging.info(f"Renderer | context inserted after heading='{selection.context_item.place.section_heading}' index={ctx_idx} type={selection.context_item.type}")

    def _section_bounds(lines: List[str], heading_text: str) -> Tuple[int, int]:
        hidx = _find_heading_index(lines, heading_text)
        if hidx < 0:
            return len(lines) - 1, len(lines)
        end = hidx + 1
        while end < len(lines):
            m = SECTION_RE.match(lines[end])
            if m:
                break
            end += 1
        return hidx + 1, end

    def _is_list_item(line: str) -> bool:
        """Check if line is a list item (bullet or numbered)"""
        stripped = line.lstrip()
        return stripped.startswith('* ') or stripped.startswith('- ') or stripped.startswith('+ ') or bool(re.match(r'^\d+\.\s', stripped))
    
    def _paragraph_ranges(lines: List[str], start: int, end: int) -> List[Tuple[int, int]]:
        """Group lines into paragraph ranges, treating each list item as a separate paragraph"""
        ranges: List[Tuple[int, int]] = []
        i = start
        while i < end:
            while i < end and (lines[i].strip() == "" or _is_media_line(lines[i])):
                i += 1
            if i >= end:
                break
            
            # If this is a list item, treat it as a single-line paragraph
            if _is_list_item(lines[i]):
                j = i + 1
                while j < end and lines[j].strip() != "" and not _is_media_line(lines[j]) and not _is_list_item(lines[j]) and lines[j].startswith('  '):
                    j += 1
                ranges.append((i, j))
                i = j
            else:
                j = i
                while j < end and (lines[j].strip() != "" and not _is_media_line(lines[j]) and not _is_list_item(lines[j])):
                    j += 1
                ranges.append((i, j))
                i = j + 1
        return ranges

    def _tokenize(s: str) -> List[str]:
        return re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?", (s or "").lower())

    def _split_sentences(text: str) -> List[Tuple[int, int]]:
        spans: List[Tuple[int, int]] = []
        i = 0
        start = 0
        while i < len(text):
            ch = text[i]
            if ch in ".!?":
                prev = text[i-1] if i-1 >= 0 else ""
                nxt = text[i+1] if i+1 < len(text) else ""
                # Do not split decimals like 0.01
                if ch == "." and prev.isdigit() and nxt.isdigit():
                    i += 1
                    continue
                end = i + 1
                spans.append((start, end))
                while end < len(text) and text[end].isspace():
                    end += 1
                start = end
                i = end
                continue
            i += 1
        if start < len(text):
            spans.append((start, len(text)))
        return spans

    def _score_paragraph(text: str, kw: str, global_keywords: List[str], anchor: str) -> int:
        ptoks = set(_tokenize(text))
        ktoks = set(_tokenize(kw))
        gtoks = set(t for k in global_keywords for t in _tokenize(k))
        atoks = set(_tokenize(anchor))
        score = 0
        score += 2 * sum(1 for t in ktoks if t in ptoks)
        score += sum(1 for t in atoks if t in ptoks)
        score += sum(1 for t in gtoks if t in ptoks)
        return score

    def insert_link(anchor: str, url: str, target_heading: str, keyword: str, hint_par_idx: int | None = None, hint_sent_idx: int | None = None, used_paragraphs: Set[int] | None = None):
        start, end = _section_bounds(lines, target_heading)
        pranges = _paragraph_ranges(lines, start, end)
        if not pranges:
            idx = start
            line = lines[idx] if 0 <= idx < len(lines) else ""
            if line.strip():
                lines[idx] = f"{line} [{ anchor}]({url})"
            else:
                lines.insert(idx, f"[{anchor}]({url})")
            logging.info(f"Renderer | no paragraphs; link inserted inline at section start heading='{target_heading}' url={url}")
            return
        # Smart paragraph selection: Try hint -> Search all -> Fallback to hint/score
        chosen_idx = -1
        
        def _check_anchor_in_par(idx: int) -> bool:
            pstart, pend = pranges[idx]
            text = " ".join(lines[pstart:pend])
            return anchor.lower() in _strip_markdown_formatting(text).lower()

        # 1. Try hint paragraph
        if hint_par_idx is not None and 0 <= hint_par_idx < len(pranges) and (not used_paragraphs or hint_par_idx not in used_paragraphs):
            if _check_anchor_in_par(hint_par_idx):
                chosen_idx = hint_par_idx
            else:
                logging.info(f"DEBUG | Anchor '{anchor}' not found in hint paragraph {hint_par_idx}, searching section...")

        # 2. If not found in hint, search all other paragraphs
        if chosen_idx == -1:
            for idx in range(len(pranges)):
                if used_paragraphs and idx in used_paragraphs:
                    continue
                if _check_anchor_in_par(idx):
                    chosen_idx = idx
                    logging.info(f"DEBUG | Found anchor '{anchor}' in paragraph {idx}")
                    break
        
        # 3. Fallback: Use hint (if valid) or best scoring paragraph
        if chosen_idx == -1:
            if hint_par_idx is not None and 0 <= hint_par_idx < len(pranges) and (not used_paragraphs or hint_par_idx not in used_paragraphs):
                chosen_idx = hint_par_idx
                logging.info(f"DEBUG | Anchor not found anywhere, falling back to hint paragraph {chosen_idx}")
            else:
                best_idx = None
                best_score = -1
                for idx, (pstart, pend) in enumerate(pranges):
                    if used_paragraphs and idx in used_paragraphs:
                        continue
                    text = " ".join(lines[pstart:pend])
                    score = _score_paragraph(text, keyword, keywords, anchor)
                    if score > best_score:
                        best_score = score
                        best_idx = idx
                if best_idx is None:
                    best_idx = 0
                chosen_idx = best_idx
                logging.info(f"DEBUG | Anchor not found anywhere, falling back to scored paragraph {chosen_idx}")
        pstart, pend = pranges[chosen_idx]
        original_lines = lines[pstart:pend]
        paragraph = " ".join(original_lines)
        paragraph_lower = paragraph.lower()
        
        anchor_lower = anchor.lower()
        inserted = False
        
        logging.info(f"DEBUG | Searching for anchor='{anchor}' in paragraph (len={len(paragraph)})")
        
        pos = paragraph_lower.find(anchor_lower)
        if pos >= 0:
            logging.info(f"DEBUG | Found anchor in paragraph at position {pos}")
            # Check word boundaries
            endpos = pos + len(anchor_lower)
            before_char = paragraph_lower[pos-1] if pos > 0 else ' '
            after_char = paragraph_lower[endpos] if endpos < len(paragraph_lower) else ' '
            
            # More lenient boundary check: just ensure not in middle of a word
            is_word_start = not before_char.isalnum()
            is_word_end = not after_char.isalnum() or after_char in ' .,;:!?-—'
            
            logging.info(f"DEBUG | before='{before_char}' after='{after_char}' word_start={is_word_start} word_end={is_word_end}")
            
            if is_word_start and is_word_end:
                before = paragraph[:pos]
                middle = paragraph[pos:endpos]
                after = paragraph[endpos:]
                
                # Handle possessives
                possessive = ""
                rest_after = after
                if rest_after.startswith("'s") or rest_after.startswith("'s"):
                    possessive = rest_after[:2]
                    rest_after = rest_after[2:]
                
                new_paragraph = f"{before}[{middle}]({url}){possessive}{rest_after}"
                lines[pstart:pend] = [new_paragraph]
                
                inserted = True
                logging.info(
                    f"Renderer | link inserted in paragraph section='{target_heading}' paragraph_idx={chosen_idx} anchor='{anchor}' url={url}"
                )
            else:
                logging.warning(f"DEBUG | Word boundary check FAILED - before_char='{before_char}' after_char='{after_char}'")
        else:
            logging.warning(f"DEBUG | Anchor '{anchor}' NOT FOUND in paragraph")
        
        # FALLBACK: Try sentence-level matching 
        if not inserted:
            logging.info("DEBUG | Falling back to sentence-level matching")
            spans = _split_sentences(paragraph)
            target_sentence_idx = hint_sent_idx if (hint_sent_idx is not None and 0 <= hint_sent_idx < len(spans)) else (0 if spans else None)
            if spans and target_sentence_idx is not None:
                sent_start, sent_end = spans[target_sentence_idx]
                sentence = paragraph[sent_start:sent_end]
                lower = sentence.lower()
                
                pos = lower.find(anchor_lower)
                if pos >= 0:
                    endpos = pos + len(anchor_lower)
                    before_char = lower[pos-1] if pos > 0 else ' '
                    after_char = lower[endpos] if endpos < len(lower) else ' '
                    
                    if not before_char.isalnum() and (not after_char.isalnum() or after_char in ' .,;:!?'):
                        before = sentence[:pos]
                        middle = sentence[pos:endpos]
                        after = sentence[endpos:]
                        possessive = ""
                        rest_after = after
                        if rest_after.startswith("'s") or rest_after.startswith("'s"):
                            possessive = rest_after[:2]
                            rest_after = rest_after[2:]
                        new_sentence = f"{before}[{middle}]({url}){possessive}{rest_after}"
                        new_paragraph = f"{paragraph[:sent_start]}{new_sentence}{paragraph[sent_end:]}"
                        
                        lines[pstart:pend] = [new_paragraph]
                        
                        inserted = True
                        logging.info(
                            f"Renderer | link inserted in sentence section='{target_heading}' paragraph_idx={chosen_idx} sentence_idx={target_sentence_idx} url={url}"
                        )
        
        # LAST RESORT: Token-based fallback
        if not inserted:
            logging.info("DEBUG | Falling back to token-based matching")
            ktoks = sorted(_tokenize(anchor), key=len, reverse=True)
            for tok in ktoks:
                if len(tok) < 3:
                    continue
                pos = paragraph_lower.find(tok)
                if pos >= 0:
                    endpos = pos + len(tok)
                    before_char = paragraph_lower[pos-1] if pos > 0 else ' '
                    after_char = paragraph_lower[endpos] if endpos < len(paragraph_lower) else ' '
                    
                    if not before_char.isalnum() and (not after_char.isalnum() or after_char in ' .,;:!?-'):
                        before = paragraph[:pos]
                        middle = paragraph[pos:endpos]
                        after = paragraph[endpos:]
                        new_paragraph = f"{before}[{middle}]({url}){after}"
                        
                        lines[pstart:pend] = [new_paragraph]
                        inserted = True
                        logging.info(
                            f"Renderer | link inserted via token section='{target_heading}' token='{tok}' url={url}"
                        )
                        break
        
        if not inserted:
            if pend > pstart:
                last_line = lines[pend-1].rstrip()
                tail_space = " " if last_line and not last_line.endswith(" ") else ""
                lines[pend-1] = last_line + f"{tail_space}([{anchor}]({url}))"
            logging.warning(
                f"Renderer | link appended at end (anchor not found anywhere) section='{target_heading}' paragraph_idx={chosen_idx} anchor='{anchor}' url={url}"
            )

    used_by_section: Dict[str, Set[int]] = {}
    for link in selection.links:
        target = link.place.section_heading or selection.context_item.place.section_heading
        key = (target or "").strip().lower()
        used = used_by_section.setdefault(key, set())

        start, end = _section_bounds(lines, target)
        pranges = _paragraph_ranges(lines, start, end)
        hint_idx = link.place.paragraph_index if (link.place and isinstance(link.place.paragraph_index, int)) else None

        hint_sent = link.place.sentence_index if (link.place and isinstance(link.place.sentence_index, int)) else None
        insert_link(link.anchor, link.url, target, link.keyword, hint_par_idx=hint_idx, hint_sent_idx=hint_sent, used_paragraphs=used)

        # After insertion, mark the paragraph as used if it was a valid index
        if hint_idx is not None and 0 <= hint_idx < len(pranges) and hint_idx not in used:
            used.add(hint_idx)
        else:
            best_idx = None
            best_score = -1
            for idx, (pstart, pend) in enumerate(pranges):
                if idx in used:
                    continue
                text = " ".join(lines[pstart:pend])
                score = _score_paragraph(text, link.keyword, keywords, link.anchor)
                if score > best_score:
                    best_score = score
                    best_idx = idx
            if best_idx is not None:
                used.add(best_idx)

    full = "\n".join(lines)
    present_urls = _extract_urls(full)
    for link in selection.links:
        if _normalize_url(link.url) not in present_urls:
            start, end = _section_bounds(lines, link.place.section_heading or selection.context_item.place.section_heading)
            lines.insert(end, f"[{link.anchor}]({link.url})")
            lines.insert(end, "")
            full = "\n".join(lines)
            present_urls = _extract_urls(full)
            logging.info(
                f"Renderer | link url missing post-insert; appended at end of section heading='{link.place.section_heading or selection.context_item.place.section_heading}' url={link.url}"
            )

    result = "\n".join(lines)
    result = re.sub(r"\s*—\s*", " ", result)
    return result
def _is_media_line(line: str) -> bool:
    s = (line or "").strip()
    return s.startswith("▶ ") or s.startswith("![")
