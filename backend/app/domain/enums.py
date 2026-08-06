from enum import StrEnum


class Role(StrEnum):
    STUDENT = "STUDENT"
    TEACHER = "TEACHER"


class VersionState(StrEnum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    WITHDRAWN = "WITHDRAWN"


class AudienceAge(StrEnum):
    AGE_7_11 = "AGE_7_11"
    AGE_12_17 = "AGE_12_17"


class Tone(StrEnum):
    FRIENDLY = "FRIENDLY"
    CURIOUS = "CURIOUS"
    COACH_LIKE = "COACH_LIKE"


class ResponseLength(StrEnum):
    SHORT = "SHORT"
    BALANCED = "BALANCED"


class AgentTemplate(StrEnum):
    KNOWLEDGE_EXPLORER = "KNOWLEDGE_EXPLORER"


class IngestionState(StrEnum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    READY = "READY"
    FAILED = "FAILED"


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    READY = "READY"
    FAILED = "FAILED"
    RETIRED = "RETIRED"
