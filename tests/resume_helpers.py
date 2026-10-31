"""Small builders and sample data shared by the resume studio tests."""

from typing import Any

from pv_domain.resume_doc import blank_document, document_from_entries, validate_document


def text_node(text: str, *marks: str) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "text", "text": text}
    if marks:
        node["marks"] = [{"type": m} for m in marks]
    return node


def para(*nodes: dict[str, Any]) -> dict[str, Any]:
    return {"type": "paragraph", "content": list(nodes)}


def bullets(*lines: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {"type": "listItem", "content": [para(text_node(line))]} for line in lines
                ],
            }
        ],
    }


ENTRIES_FOR_RENDER: list[tuple[str, dict[str, Any]]] = [
    (
        "work",
        {
            "company": "Kestrel Analytics",
            "title": "Data Intern",
            "location": "Bengaluru",
            "start_date": "2025-06",
            "end_date": "2025-08",
            "highlights": [
                "Cleaned six CSV sources with pandas",
                "Wrote SQL joins over 1.2 million rows",
            ],
        },
    ),
    (
        "education",
        {
            "institution": "BMS College of Engineering",
            "degree": "B.E.",
            "field_of_study": "Computer Science",
            "end_date": "2026",
        },
    ),
    (
        "project",
        {
            "name": "Churn model",
            "description": "Predicts churn.",
            "technologies": ["Python", "pandas"],
        },
    ),
    ("skill", {"name": "Python", "category": "Languages"}),
    ("skill", {"name": "SQL", "category": "Languages"}),
]


def sample_document(name: str = "Asha Rao", template: str = "classic") -> dict[str, Any]:
    doc = document_from_entries(ENTRIES_FOR_RENDER, name=name, template=template)
    doc["header"]["headline"] = "Data analyst"
    doc["header"]["contacts"] = ["asha@example.com", "+91 90000 00000", "Bengaluru, India"]
    return validate_document(doc)


def empty_document(name: str = "") -> dict[str, Any]:
    return validate_document(blank_document("classic", name))
