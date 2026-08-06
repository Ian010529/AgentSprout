"""Pure deterministic safety policy shared by Studio and public chat entry points."""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\s().-]*){7,15}(?!\d)")
ADDRESS_RE = re.compile(
    r"(?i)\b\d{1,6}\s+[a-z0-9][a-z0-9 .'-]{1,60}\s+"
    r"(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|court|ct|boulevard|blvd)\b"
)
PII_REQUEST_RE = re.compile(
    r"(?i)\b(?:tell|show|give|share|collect|find|reveal|what(?:'s| is))\b.{0,40}"
    r"\b(?:email|e-mail|phone|telephone|home address|street address)\b"
)

SAFE_PRIVACY_ANSWER = (
    "Keep personal contact details private. I can't use or repeat an email, phone number, "
    "or home address. Ask a trusted adult if you need help sharing information safely."
)
SAFE_MODERATION_ANSWER = (
    "I can't help with that request. We can switch to a safe ocean-learning question instead. "
    "If someone may be in immediate danger, tell a trusted adult or contact local emergency help."
)
SAFE_INJECTION_ANSWER = (
    "I can't reveal hidden instructions or ignore the safety and knowledge rules. "
    "I can still help with a question supported by the Ocean Literacy source."
)
SAFE_OUT_OF_KNOWLEDGE_ANSWER = (
    "I couldn't find enough support for that in the uploaded Ocean Literacy source. "
    "Try asking about ocean systems, climate, life, exploration, or people's connection "
    "to the ocean."
)


def detect_pii(message: str) -> str | None:
    if EMAIL_RE.search(message):
        return "PII_EMAIL"
    if ADDRESS_RE.search(message):
        return "PII_ADDRESS"
    if PHONE_RE.search(message):
        return "PII_PHONE"
    if PII_REQUEST_RE.search(message):
        return "PII_REQUEST"
    return None
