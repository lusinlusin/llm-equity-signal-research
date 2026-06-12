from __future__ import annotations

import re
from dataclasses import dataclass, field


_TARGET_BLOCK_CHARS = 700
_MATCH_THRESHOLD = 0.50
_UNCHANGED_THRESHOLD = 0.85


@dataclass
class RiskSectionDiff:
    """Deterministic year-over-year diff between two Item 1A texts."""

    similarity: float
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[tuple[str, str]] = field(default_factory=list)
    n_current_blocks: int = 0
    n_prior_blocks: int = 0

    @property
    def added_chars(self) -> int:
        return sum(len(block) for block in self.added)

    @property
    def removed_chars(self) -> int:
        return sum(len(block) for block in self.removed)

    @property
    def modified_chars(self) -> int:
        return sum(len(before) + len(after) for before, after in self.modified)


def _normalize_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.?!])\s+(?=[A-Z“\"(])", normalized)
    return [part.strip() for part in parts if part.strip()]


def split_into_blocks(text: str, target_chars: int = _TARGET_BLOCK_CHARS) -> list[str]:
    """Group sentences into blocks of roughly ``target_chars`` characters.

    SEC-extracted Item 1A text is often a single line with no paragraph
    markers, so blocks are built from sentence groups rather than newlines.
    """
    sentences = _split_sentences(text)
    blocks: list[str] = []
    buffer = ""
    for sentence in sentences:
        buffer = f"{buffer} {sentence}".strip() if buffer else sentence
        if len(buffer) >= target_chars:
            blocks.append(buffer)
            buffer = ""
    if buffer:
        if blocks and len(buffer) < target_chars // 2:
            blocks[-1] = f"{blocks[-1]} {buffer}"
        else:
            blocks.append(buffer)
    return blocks


def _word_set(text: str) -> frozenset[str]:
    return frozenset(_normalize_words(text))


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    union = len(left | right)
    if union == 0:
        return 0.0
    return len(left & right) / union


def shingle_similarity(current_text: str, prior_text: str, shingle_size: int = 3) -> float:
    """Jaccard similarity over word shingles, in the style of Lazy Prices."""
    current_words = _normalize_words(current_text)
    prior_words = _normalize_words(prior_text)
    if len(current_words) < shingle_size or len(prior_words) < shingle_size:
        return 0.0

    current_shingles = {
        tuple(current_words[i : i + shingle_size])
        for i in range(len(current_words) - shingle_size + 1)
    }
    prior_shingles = {
        tuple(prior_words[i : i + shingle_size])
        for i in range(len(prior_words) - shingle_size + 1)
    }
    union = len(current_shingles | prior_shingles)
    if union == 0:
        return 0.0
    return len(current_shingles & prior_shingles) / union


def diff_risk_sections(current_text: str, prior_text: str) -> RiskSectionDiff:
    """Match current blocks to prior blocks and classify added/removed/modified.

    Blocks are matched greedily by word-set Jaccard similarity: a current block
    with no prior match above ``_MATCH_THRESHOLD`` is added; a matched block
    below ``_UNCHANGED_THRESHOLD`` is modified; unmatched prior blocks are removed.
    """
    current_blocks = split_into_blocks(current_text)
    prior_blocks = split_into_blocks(prior_text)
    diff = RiskSectionDiff(
        similarity=shingle_similarity(current_text, prior_text),
        n_current_blocks=len(current_blocks),
        n_prior_blocks=len(prior_blocks),
    )

    prior_sets = [_word_set(block) for block in prior_blocks]
    prior_used = [False] * len(prior_blocks)
    for block in current_blocks:
        block_set = _word_set(block)
        best_index = -1
        best_score = 0.0
        for index, prior_set in enumerate(prior_sets):
            if prior_used[index]:
                continue
            score = _jaccard(block_set, prior_set)
            if score > best_score:
                best_score = score
                best_index = index

        if best_index < 0 or best_score < _MATCH_THRESHOLD:
            diff.added.append(block)
        else:
            prior_used[best_index] = True
            if best_score < _UNCHANGED_THRESHOLD:
                diff.modified.append((prior_blocks[best_index], block))

    for index, prior_block in enumerate(prior_blocks):
        if not prior_used[index]:
            diff.removed.append(prior_block)

    return diff


def _take_blocks(blocks: list[str], budget_chars: int) -> str:
    taken: list[str] = []
    used = 0
    for block in blocks:
        if used >= budget_chars:
            break
        clipped = block[: budget_chars - used]
        taken.append(clipped)
        used += len(clipped)
    return "\n\n".join(taken) if taken else "(none)"


def format_diff_for_prompt(diff: RiskSectionDiff, max_total_chars: int = 12_000) -> dict[str, str]:
    """Render diff sections into bounded prompt text, longest changes first."""
    added = sorted(diff.added, key=len, reverse=True)
    removed = sorted(diff.removed, key=len, reverse=True)
    modified = sorted(diff.modified, key=lambda pair: len(pair[0]) + len(pair[1]), reverse=True)

    added_budget = int(max_total_chars * 0.45)
    removed_budget = int(max_total_chars * 0.20)
    modified_budget = max_total_chars - added_budget - removed_budget

    modified_blocks = [f"PRIOR: {before}\n=> CURRENT: {after}" for before, after in modified]
    return {
        "added": _take_blocks(added, added_budget),
        "removed": _take_blocks(removed, removed_budget),
        "modified": _take_blocks(modified_blocks, modified_budget),
    }
