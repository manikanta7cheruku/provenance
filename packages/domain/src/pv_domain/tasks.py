"""Names of background task types and the rules that depend on them."""

TASK_SEND_EMAIL = "send_email"
TASK_DEMO = "system.demo"
TASK_PARSE_RESUME = "parse_resume"
TASK_EMBED_EVIDENCE = "embed_evidence"
TASK_EXTRACT_JOB = "extract_job"
TASK_ANALYZE_JOB = "analyze_job"
TASK_RENDER_RESUME = "render_resume_pdf"
TASK_TAILOR_RESUME = "tailor_resume"
TASK_POLL_SOURCE = "poll_source"
TASK_IMPORT_FILE = "import_file"
TASK_IMPORT_URL = "import_url"
TASK_DRAFT_APPLICATION = "draft_application"
TASK_SEND_SHORTLIST = "send_shortlist"
TASK_SYNC_GITHUB = "sync_github"
TASK_PREPARE_JOB = "prepare_job"
TASK_BUILD_REPORT = "build_report"
TASK_DELETE_ACCOUNT = "delete_account"

# These carry a one-time secret (a link token) that is erased when the task finishes
# or dead-letters, so replaying them is impossible. The user must ask for a new link.
NON_REQUEUEABLE = frozenset({TASK_SEND_EMAIL})
