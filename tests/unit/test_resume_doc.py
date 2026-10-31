"""The resume document model: validation, rich text, a first draft from the profile."""

import copy
from typing import Any

import pytest
from resume_helpers import para, text_node

from pv_domain.resume_doc import (
    MAX_BLOCKS_PER_SECTION,
    MAX_CONTACTS,
    MAX_SECTIONS,
    ResumeDocError,
    blank_document,
    contrast_on_white,
    document_from_entries,
    document_text,
    rich_to_text,
    validate_document,
)


def doc_with(body: dict[str, Any] | None = None, **block: Any) -> dict[str, Any]:
    document = blank_document("classic", "Asha Rao")
    document["sections"] = [
        {
            "id": "s1",
            "kind": "experience",
            "title": "Experience",
            "blocks": [
                {
                    "id": "b1",
                    "heading": "Data Intern",
                    "subheading": "Kestrel",
                    "dates": "2025",
                    "location": "",
                    "body": body,
                    **block,
                }
            ],
        }
    ]
    return document


def problems_of(raw: Any) -> dict[str, str]:
    with pytest.raises(ResumeDocError) as raised:
        validate_document(raw)
    return raised.value.problems


class TestValidation:
    def test_a_blank_document_is_valid_and_comes_back_clean(self) -> None:
        clean = validate_document(blank_document("modern", "Asha"))
        assert clean["style"]["template"] == "modern" and clean["header"]["name"] == "Asha"
        assert clean["sections"] == []

    def test_the_copy_is_clean_and_the_input_is_not_changed(self) -> None:
        raw = doc_with({"type": "doc", "content": [para(text_node("Built things", "bold"))]})
        before = copy.deepcopy(raw)
        clean = validate_document(raw)
        assert raw == before
        assert clean["sections"][0]["blocks"][0]["body"]["content"][0]["content"][0]["marks"] == [
            {"type": "bold"}
        ]

    def test_unknown_keys_are_dropped_not_stored(self) -> None:
        raw = doc_with()
        raw["evil"] = "<script>alert(1)</script>"
        raw["sections"][0]["blocks"][0]["onclick"] = "x"
        clean = validate_document(raw)
        assert "evil" not in clean and "onclick" not in clean["sections"][0]["blocks"][0]

    @pytest.mark.parametrize("bad", [None, [], "text", 3])
    def test_a_document_must_be_an_object(self, bad: Any) -> None:
        assert "document" in problems_of(bad)

    def test_control_characters_are_removed_from_text(self) -> None:
        raw = doc_with(heading="Data\x00 In\x07tern")
        assert validate_document(raw)["sections"][0]["blocks"][0]["heading"] == "Data Intern"

    def test_too_long_text_is_refused_next_to_the_field(self) -> None:
        problems = problems_of(doc_with(heading="x" * 200))
        assert problems["sections.0.blocks.0.heading"].startswith("This is too long")

    def test_limits_on_sections_blocks_and_contacts(self) -> None:
        many = blank_document()
        many["sections"] = [
            {"kind": "custom", "title": "T", "blocks": []} for _ in range(MAX_SECTIONS + 1)
        ]
        assert "sections" in problems_of(many)
        crowded = doc_with()
        crowded["sections"][0]["blocks"] = [
            {"heading": "x"} for _ in range(MAX_BLOCKS_PER_SECTION + 1)
        ]
        assert "sections.0.blocks" in problems_of(crowded)
        contacts = blank_document()
        contacts["header"]["contacts"] = ["a@b.co"] * (MAX_CONTACTS + 1)
        assert "header.contacts" in problems_of(contacts)

    def test_an_unknown_section_kind_becomes_custom_and_ids_are_made_unique(self) -> None:
        raw = doc_with()
        raw["sections"][0]["kind"] = "banana"
        raw["sections"].append(copy.deepcopy(raw["sections"][0]))
        clean = validate_document(raw)
        assert {s["kind"] for s in clean["sections"]} == {"custom"}
        ids = [s["id"] for s in clean["sections"]] + [
            b["id"] for s in clean["sections"] for b in s["blocks"]
        ]
        assert len(ids) == len(set(ids))

    def test_bad_ids_are_replaced(self) -> None:
        raw = doc_with()
        raw["sections"][0]["id"] = "<img src=x>"
        assert validate_document(raw)["sections"][0]["id"] != "<img src=x>"

    def test_the_whole_resume_has_a_size_limit(self) -> None:
        raw = doc_with()
        raw["sections"][0]["blocks"] = [
            {"heading": "h", "body": {"type": "doc", "content": [para(text_node("w" * 5000))]}}
            for _ in range(8)
        ]
        assert "document" in problems_of(raw)


class TestRichText:
    def test_paragraphs_lists_marks_and_breaks_are_kept(self) -> None:
        body = {
            "type": "doc",
            "content": [
                para(
                    text_node("Hello ", "bold", "italic"), {"type": "hardBreak"}, text_node("world")
                ),
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [para(text_node("one"))]},
                        {"type": "listItem", "content": [para(text_node("two", "highlight"))]},
                    ],
                },
                {
                    "type": "orderedList",
                    "content": [{"type": "listItem", "content": [para(text_node("first"))]}],
                },
            ],
        }
        clean = validate_document(doc_with(body))["sections"][0]["blocks"][0]["body"]
        assert rich_to_text(clean) == "Hello \nworld\n- one\n- two\n1. first"

    @pytest.mark.parametrize(
        "node",
        [
            {"type": "image", "attrs": {"src": "http://evil.example/x.png"}},
            {"type": "heading", "content": []},
            {"type": "codeBlock", "content": []},
            {"type": "html", "content": "<b>x</b>"},
        ],
    )
    def test_nodes_outside_the_whitelist_are_refused(self, node: dict[str, Any]) -> None:
        problems = problems_of(doc_with({"type": "doc", "content": [node]}))
        assert "sections.0.blocks.0.body.0" in problems

    def test_marks_outside_the_whitelist_are_refused(self) -> None:
        body = {"type": "doc", "content": [para(text_node("x", "link"))]}
        assert problems_of(doc_with(body))

    def test_a_link_mark_cannot_carry_an_address_in(self) -> None:
        body = {
            "type": "doc",
            "content": [
                para(
                    {
                        "type": "text",
                        "text": "x",
                        "marks": [{"type": "link", "attrs": {"href": "javascript:alert(1)"}}],
                    }
                )
            ],
        }
        assert problems_of(doc_with(body))

    def test_deep_nesting_and_huge_bodies_are_refused(self) -> None:
        node: dict[str, Any] = para(text_node("deep"))
        for _ in range(8):
            node = {"type": "bulletList", "content": [{"type": "listItem", "content": [node]}]}
        assert problems_of(doc_with({"type": "doc", "content": [node]}))
        wide = {"type": "doc", "content": [para(text_node("x")) for _ in range(500)]}
        assert problems_of(doc_with(wide))

    def test_an_empty_body_becomes_none(self) -> None:
        assert (
            validate_document(doc_with({"type": "doc", "content": []}))["sections"][0]["blocks"][0][
                "body"
            ]
            is None
        )


class TestStyle:
    def test_choices_must_come_from_the_lists(self) -> None:
        raw = blank_document()
        raw["style"]["font_pair"] = "comic-sans"
        raw["style"]["template"] = "../../etc"
        problems = problems_of(raw)
        assert set(problems) == {"style.font_pair", "style.template"}

    def test_the_accent_must_be_a_hex_color_that_can_be_read_on_white(self) -> None:
        raw = blank_document()
        raw["style"]["accent"] = "red"
        assert "style.accent" in problems_of(raw)
        raw["style"]["accent"] = "#ffee88"
        assert "too light" in problems_of(raw)["style.accent"]
        raw["style"]["accent"] = "#1F3D7A"
        assert validate_document(raw)["style"]["accent"] == "#1f3d7a"

    def test_contrast_of_known_colors(self) -> None:
        assert contrast_on_white("#000000") == pytest.approx(21.0, rel=0.01)
        assert contrast_on_white("#ffffff") == pytest.approx(1.0, rel=0.01)


class TestFirstDraft:
    ENTRIES: list[tuple[str, dict[str, Any]]] = [
        (
            "work",
            {
                "company": "Kestrel",
                "title": "Data Intern",
                "start_date": "2025-06",
                "end_date": "2025-08",
                "highlights": ["Cleaned six CSV sources", "Wrote SQL joins"],
            },
        ),
        (
            "education",
            {
                "institution": "BMS College",
                "degree": "B.E.",
                "field_of_study": "Computer Science",
                "end_date": "2026",
                "grade": "8.4 CGPA",
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
        ("certification", {"name": "AWS Cloud Practitioner", "issuer": "Amazon"}),
        ("link", {"label": "GitHub", "url": "https://github.com/asha"}),
    ]

    def test_every_word_comes_from_an_entry(self) -> None:
        doc = document_from_entries(self.ENTRIES, name="Asha Rao")
        text = document_text(doc)
        for expected in (
            "Data Intern",
            "Kestrel",
            "2025-06 to 2025-08",
            "Cleaned six CSV sources",
            "B.E. Computer Science",
            "BMS College",
            "Grade: 8.4 CGPA",
            "Churn model",
            "Python, pandas",
            "Python, SQL",
            "AWS Cloud Practitioner",
            "Amazon",
            "GitHub: https://github.com/asha",
        ):
            assert expected in text
        assert doc["header"]["name"] == "Asha Rao"

    def test_sections_come_in_a_sensible_order_and_empty_ones_are_left_out(self) -> None:
        doc = document_from_entries(self.ENTRIES)
        assert [s["kind"] for s in doc["sections"]] == [
            "experience", "education", "projects", "skills", "certifications",
        ]  # fmt: skip
        only = document_from_entries([("skill", {"name": "Go"})])
        assert [s["kind"] for s in only["sections"]] == ["skills"]

    def test_an_empty_profile_gives_a_blank_valid_document(self) -> None:
        doc = document_from_entries([])
        assert doc["sections"] == [] and validate_document(doc)

    def test_highlights_become_bullets(self) -> None:
        doc = document_from_entries(self.ENTRIES)
        body = doc["sections"][0]["blocks"][0]["body"]
        assert (
            body["content"][0]["type"] == "bulletList" and len(body["content"][0]["content"]) == 2
        )
