"""Application text drafts: a cover note or an answer to a common question, written for one job.

Pure code. The model only proposes wording (pv_llm.draft). What is checked, and what the person sees,
is decided here:

  - A draft is made only for a job whose evidence check is complete, and it may use only the evidence
    that supported that job's requirements. A requirement with no support is never claimed.
  - Every claim in the draft (a number, a name or tool, a word the job asked for) is checked against
    that evidence and the job's own heading (its title, company and place). A claim in neither is
    listed for the person, in their own words. The check runs again every time they edit.
  - A draft is always labelled as a draft. The product never sends it anywhere and never applies.
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from pv_domain.tailoring import Verification, verify_text

KIND_COVER_NOTE = "cover_note"
KIND_ANSWER = "answer"
KINDS = (KIND_COVER_NOTE, KIND_ANSWER)

MAX_DRAFTS_PER_JOB = 8
MAX_BODY_CHARS = 6000
MAX_QUESTION_CHARS = 300
MIN_BODY_CHARS = 40

DRAFT_LABEL = (
    "Draft. Written by AI from your own evidence. Check every line. Nothing is sent anywhere."
)

COMMON_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("why_role", "Why are you interested in this role?"),
    ("why_company", "Why do you want to work here?"),
    ("strength", "What is your strongest skill for this role?"),
    ("project", "Tell us about a project you are proud of."),
    ("problem", "Describe a problem you solved and how you solved it."),
)


class DraftStatus(StrEnum):
    QUEUED = "queued"
    WORKING = "working"
    READY = "ready"
    FAILED = "failed"


class DraftErrorCode(StrEnum):
    ANALYSIS_NEEDED = "analysis_needed"
    NO_EVIDENCE = "no_evidence"
    AI_NOT_CONFIGURED = "ai_not_configured"
    AI_UNAVAILABLE = "ai_unavailable"
    AI_BAD_OUTPUT = "ai_bad_output"


DRAFT_ERROR_MESSAGES: dict[str, str] = {
    DraftErrorCode.ANALYSIS_NEEDED: (
        "Check this job against your evidence first. A draft can only use what the check found."
    ),
    DraftErrorCode.NO_EVIDENCE: (
        "Your evidence does not support any requirement of this job yet, so there is nothing true "
        "to write from. Add evidence to your profile and check the job again."
    ),
    DraftErrorCode.AI_NOT_CONFIGURED: "The writing service is not set up yet. Try again later.",
    DraftErrorCode.AI_UNAVAILABLE: "The writing service did not answer. Try again in a few minutes.",
    DraftErrorCode.AI_BAD_OUTPUT: "The writing service gave an answer we could not use. Try again.",
}

# Words a letter uses that say nothing about the person. They are never flagged as claims.
LETTER_WORDS = (
    "Dear Hiring Manager Team Recruiter Sir Madam Hello Hi Regards Sincerely Thanks Thank You "
    "Kind Best Yours Faithfully Cordially Respectfully"
)

_SPACES = re.compile(r"[ \t\f\v]+")
_BLANKS = re.compile(r"\n{3,}")
_KEY_JUNK = re.compile(r"[^a-z0-9 ]+")


def clean_question(raw: str) -> str:
    """A question as one tidy line, or an empty string when there is nothing usable."""
    text = unicodedata.normalize("NFC", raw)
    text = "".join(ch if ch >= " " and ch != "\x7f" else " " for ch in text)
    return " ".join(text.split())[:MAX_QUESTION_CHARS]


def question_key(question: str) -> str:
    """What makes two questions the same question: case, punctuation and spacing do not."""
    folded = _KEY_JUNK.sub(" ", clean_question(question).casefold())
    return " ".join(folded.split())[:120]


def clean_body(raw: str) -> str:
    """A draft's text with hidden characters removed and blank lines tidied. Paragraphs are kept."""
    text = unicodedata.normalize("NFC", raw).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or (ch >= " " and ch != "\x7f"))
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANKS.sub("\n\n", "\n".join(lines)).strip()


def word_count(text: str) -> int:
    return len(text.split())


@dataclass(frozen=True)
class JobHeading:
    title: str
    company: str
    location: str

    def texts(self) -> list[str]:
        return [t for t in (self.title, self.company, self.location) if t]


def verify_draft(
    body: str, *, evidence: list[str], heading: JobHeading, job_words: set[str]
) -> Verification:
    """Check every claim in a draft against the person's evidence and the job's own heading."""
    return verify_text(
        [body],
        before=[*heading.texts(), LETTER_WORDS],
        evidence=evidence,
        job_words=job_words,
    )
