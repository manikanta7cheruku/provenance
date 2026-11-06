"""The built-in resume reader: plain rules, used when the AI reader is not set up."""

from pv_domain.resume_rules import parse_resume_rules

RESUME = """Asha Rao
Bengaluru | asha@example.com | github.com/asharao | linkedin.com/in/asha-rao

SUMMARY
Final year student who likes data.

EDUCATION
Ramaiah Institute of Technology, Bengaluru
B.Tech in Computer Science  2022 - 2026
CGPA: 8.7/10

EXPERIENCE
Data Intern | Acme Analytics   Jun 2025 - Aug 2025
• Built a dashboard that cut weekly report time from 4 hours to 30 minutes
• Cleaned 200k rows of sales data with pandas

Backend Developer - Zeta Labs   2024 - Present
• Wrote REST endpoints in FastAPI

PROJECTS
Job Tracker | Python, FastAPI, Postgres
• Tracks applications and sends reminders
• Used by 40 classmates
Tech: Docker, Redis

SKILLS
Languages: Python, SQL, TypeScript
Tools: Git, Docker

CERTIFICATIONS
AWS Cloud Practitioner - Amazon Web Services 2024

ACHIEVEMENTS
• Winner, Smart India Hackathon 2024
"""


def _of(outcome, kind):
    return [data for entry_type, data in outcome.entries if entry_type == kind]


def test_reads_the_main_sections() -> None:
    outcome = parse_resume_rules(RESUME)
    education = _of(outcome, "education")
    assert education and education[0]["institution"].startswith("Ramaiah Institute")
    assert "B.Tech" in education[0]["degree"]
    assert education[0]["start_date"] == "2022" and education[0]["end_date"] == "2026"
    assert education[0]["grade"].startswith("8.7")

    internships = _of(outcome, "internship")
    assert internships[0]["company"] == "Acme Analytics"
    assert internships[0]["title"] == "Data Intern"
    assert internships[0]["start_date"] == "2025-06"
    assert len(internships[0]["highlights"]) == 2

    work = _of(outcome, "work")
    assert work[0]["title"] == "Backend Developer"
    assert work[0]["company"] == "Zeta Labs"
    assert work[0]["end_date"] == "present"

    projects = _of(outcome, "project")
    assert projects[0]["name"] == "Job Tracker"
    assert "Redis" in projects[0]["technologies"]

    names = {s["name"] for s in _of(outcome, "skill")}
    assert {"Python", "SQL", "Git", "Docker"} <= names
    assert _of(outcome, "certification")[0]["name"] == "AWS Cloud Practitioner"
    assert _of(outcome, "achievement")
    labels = {link["label"] for link in _of(outcome, "link")}
    assert {"GitHub", "LinkedIn"} <= labels


def test_never_adds_words_the_resume_lacks() -> None:
    outcome = parse_resume_rules(RESUME)
    text = RESUME.lower()
    for _kind, data in outcome.entries:
        for name, value in data.items():
            if name.endswith("date"):
                continue  # dates are rewritten as YYYY-MM
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, str) and not item.startswith("https://"):
                    assert item.lower() in text or all(w in text for w in item.lower().split())


def test_empty_or_unstructured_text_gives_no_entries() -> None:
    assert (
        parse_resume_rules("just a paragraph with no headings at all, nothing to read").entries
        == []
    )
