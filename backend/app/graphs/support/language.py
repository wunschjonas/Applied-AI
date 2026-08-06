"""Shared language constraints for German marketing output."""

from __future__ import annotations

import re

# CJK + other non-Latin scripts that models sometimes emit instead of German.
NON_GERMAN_SCRIPT_RE = re.compile(
    r"[\u0400-\u04FF\u0600-\u06FF\u3040-\u30FF\u3400-\u9FFF\uAC00-\uD7AF\uF900-\uFAFF]"
)

GERMAN_OUTPUT_RULE = (
    "Reply EXCLUSIVELY in German (Hochdeutsch). "
    "Never use Chinese, Japanese, Korean, Cyrillic, Arabic, or other non-German languages — "
    "not even in hashtags, CTAs, or single words."
)

GERMAN_COPY_RULE = (
    "Write the marketing copy EXCLUSIVELY in German (Hochdeutsch). "
    "Never use Chinese, Japanese, Korean, Cyrillic, Arabic, or mixed-script text. "
    "Hashtags must use Latin letters (German umlauts allowed: ÄÖÜäöüß), e.g. #Kraulschwimmen — "
    "never Chinese or other non-Latin hashtags."
)


def contains_non_german_script(text: str | None) -> bool:
    return bool(NON_GERMAN_SCRIPT_RE.search(text or ""))
