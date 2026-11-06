"""Plain words for a run: what it was about, what went wrong and what to do, and what a step is.

The Run Inspector shows an operational trace (steps, counts, model calls), never raw reasoning and
never the text of a job or a resume. These tables of words keep that trace readable. An unknown
value always gets a safe, generic sentence, never a blank and never the raw error text.
"""

# subject_type -> (what it is, where it lives; {id} is the subject id, None means no page)
SUBJECTS: dict[str, tuple[str, str | None]] = {
    "job_posting": ("A job", "/opportunities/{id}"),
    "resume_document": ("A resume you made in the studio", "/studio"),
    "resume": ("The resume file you uploaded", "/profile"),
    "report_export": ("A report of your jobs", "/opportunities"),
}

# error_class -> (what happened, what to do)
FAILURES: dict[str, tuple[str, str]] = {
    "JOB_READ_FAILED": (
        "The job could not be read.",
        "Check that the text is a real posting, then read it again from the job page.",
    ),
    "JOB_ANALYSIS_FAILED": (
        "The evidence check could not finish.",
        "Your profile and the job are unchanged. Run the check again from the job page.",
    ),
    "LLM_RETRYABLE": (
        "The writing service was busy or could not be reached.",
        "It was tried several times. Wait a few minutes and try again.",
    ),
    "PARSE_FAILED": (
        "Your resume could not be read.",
        "Check that the file is a PDF or Word document with selectable text, then upload it again.",
    ),
    "RESUME_EXPORT_FAILED": (
        "The PDF could not be made.",
        "Your resume is safe. Try again.",
    ),
    "REPORT_EXPORT_FAILED": (
        "The report could not be made.",
        "Your jobs are safe. Try again.",
    ),
    "INTERNAL_ERROR": (
        "Something went wrong on our side.",
        "Your data is safe. If it keeps happening, quote the reference on this page when you ask for help.",
    ),
}
_GENERIC = (
    "This run did not finish.",
    "Your data is safe. Try again, and if it keeps happening quote the reference on this page.",
)

STEP_LABELS = {
    "load_resume": "Load the resume",
    "render_pdf": "Make the PDF",
    "store_pdf": "Store the PDF",
    "gather_jobs": "Gather the jobs",
    "write_file": "Write the file",
    "store_file": "Store the file",
}


def subject_for(subject_type: str | None, subject_id: str | None) -> tuple[str | None, str | None]:
    """What the run was about, and the page for it when there is one."""
    if not subject_type or subject_type not in SUBJECTS:
        return None, None
    label, template = SUBJECTS[subject_type]
    if template is None or (("{id}" in template) and not subject_id):
        return label, None
    return label, template.format(id=subject_id)


def explain_failure(error_class: str | None, can_retry: bool) -> tuple[str, str]:
    """(what happened, what to do) for a failed run."""
    what, todo = FAILURES.get(error_class or "", _GENERIC)
    if not can_retry:
        todo += " It will not be tried again by itself."
    return what, todo


def step_label(name: str) -> str:
    return STEP_LABELS.get(name, name.replace("_", " ").strip().capitalize() or "Step")
