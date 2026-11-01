"""Rate limit policy definitions. Data, not behavior.

Limits are fixed-window counters. Values are starting points that are tuned from
measurement. The application accepts an alternative policy table, so tests and
deployments can change limits without code changes in the services.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RatePolicy:
    name: str
    limit: int
    window_seconds: int


DEFAULT_POLICIES: dict[str, RatePolicy] = {
    policy.name: policy
    for policy in (
        RatePolicy("login_ip", 5, 60),
        RatePolicy("login_email", 5, 900),
        RatePolicy("register_ip", 10, 3600),
        RatePolicy("password_reset_ip", 10, 3600),
        RatePolicy("password_reset_email", 3, 3600),
        RatePolicy("reset_confirm_ip", 10, 3600),
        RatePolicy("verify_request_user", 5, 3600),
        RatePolicy("verify_confirm_ip", 20, 3600),
        RatePolicy("password_change_user", 5, 900),
        RatePolicy("resume_upload_user", 10, 3600),
        RatePolicy("resume_reparse_user", 10, 3600),
        RatePolicy("evidence_search_user", 60, 3600),
        RatePolicy("job_paste_user", 30, 3600),
        RatePolicy("job_reanalyze_user", 20, 3600),
        RatePolicy("analysis_start_user", 20, 3600),
        RatePolicy("analysis_answer_user", 60, 3600),
        RatePolicy("analysis_feedback_user", 120, 3600),
        RatePolicy("studio_save_user", 600, 3600),
        RatePolicy("studio_preview_user", 600, 3600),
        RatePolicy("studio_export_user", 10, 3600),
        RatePolicy("tailor_start_user", 20, 3600),
        RatePolicy("search_plan_user", 60, 3600),
        RatePolicy("tailor_decide_user", 300, 3600),
    )
}
