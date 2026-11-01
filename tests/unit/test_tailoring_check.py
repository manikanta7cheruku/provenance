"""Checkpoint 2.4: what tailoring may change, and the check that a change adds no unsupported fact."""

from typing import Any

import pytest
from canvas_helpers import canvas, text_el

from pv_domain.resume_doc import blank_document, validate_document
from pv_domain.tailoring import (
    apply_unit,
    clean_lines,
    extract_claims,
    extract_units,
    find_unit,
    job_vocabulary,
    verify_text,
)


def rich_list(*lines: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": t}]}
                        ],
                    }
                    for t in lines
                ],
            }
        ],
    }


def para(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def guided() -> dict[str, Any]:
    doc = blank_document()
    doc["sections"] = [
        {
            "id": "s1",
            "kind": "summary",
            "title": "Summary",
            "blocks": [
                {
                    "id": "b0",
                    "heading": "",
                    "subheading": "",
                    "dates": "",
                    "location": "",
                    "body": {
                        "type": "doc",
                        "content": [para("Analyst who builds weekly reports.")],
                    },
                }
            ],
        },
        {
            "id": "s2",
            "kind": "experience",
            "title": "Experience",
            "blocks": [
                {
                    "id": "b1",
                    "heading": "Data Analyst",
                    "subheading": "Kestrel",
                    "dates": "2024",
                    "location": "",
                    "body": rich_list(
                        "Cut weekly reporting from two days to two hours with SQL",
                        "Built a dashboard for 6 teams",
                    ),
                }
            ],
        },
    ]
    return validate_document(doc)


class TestUnits:
    def test_bullets_and_the_summary_paragraph_are_units_and_nothing_else(self) -> None:
        units = extract_units(guided())
        assert [(u.target_id, u.kind) for u in units] == [("b0", "paragraph"), ("b1", "bullets")]
        assert units[1].label == "Data Analyst, Kestrel"
        assert units[1].lines[0].startswith("Cut weekly reporting")

    def test_a_canvas_resume_gives_its_lists_and_labelled_summaries(self) -> None:
        summary = text_el(
            "sum",
            16,
            40,
            170,
            10,
            {"type": "doc", "content": [para("Analyst.")]},
            meta={"role": "item", "sec": 0, "idx": 0, "kind": "summary"},
        )
        item = text_el(
            "it",
            16,
            60,
            170,
            20,
            {
                "type": "doc",
                "content": [para("Data Analyst"), *rich_list("Did a thing")["content"]],
            },
        )
        plain = text_el(
            "pl", 16, 90, 170, 10, {"type": "doc", "content": [para("Just a paragraph")]}
        )
        from pv_domain.resume_canvas import validate_canvas

        units = extract_units(validate_canvas(canvas(summary, item, plain)))
        assert [(u.target_id, u.kind) for u in units] == [("sum", "paragraph"), ("it", "bullets")]
        assert units[1].label == "Data Analyst"

    def test_a_unit_is_found_by_its_id(self) -> None:
        content = guided()
        assert find_unit(content, "b1:0") is not None
        assert find_unit(content, "nope:0") is None


class TestApply:
    def test_the_new_lines_replace_the_old_ones_and_the_rest_is_untouched(self) -> None:
        content = guided()
        unit = find_unit(content, "b1:0")
        assert unit is not None
        after = ["Cut weekly reporting from two days to two hours with SQL"]
        new = apply_unit(content, unit, after, unit.lines)
        assert new is not None
        assert extract_units(new)[1].lines == tuple(after)
        assert new["sections"][1]["blocks"][0]["heading"] == "Data Analyst"
        assert (
            content != new and len(extract_units(content)[1].lines) == 2
        )  # the original is unchanged
        validate_document(new)

    def test_a_part_that_changed_since_is_refused(self) -> None:
        content = guided()
        unit = find_unit(content, "b1:0")
        assert unit is not None
        assert apply_unit(content, unit, ["x"], ["something else"]) is None

    def test_a_missing_target_is_refused(self) -> None:
        content = guided()
        unit = find_unit(content, "b1:0")
        assert unit is not None
        gone = type(unit)("zzz:0", "zzz", 0, "bullets", "", ())
        assert apply_unit(content, gone, ["x"], ()) is None


class TestClaims:
    def test_numbers_names_acronyms_and_symbol_words_are_claims_and_ordinary_words_are_not(
        self,
    ) -> None:
        claims = dict(
            extract_claims("Cut costs by 40% using Python and AWS, C++ and Node.js for Acme")
        )
        assert claims["40"] == "number"
        for name in ("python", "aws", "c++", "node.js", "acme"):
            assert claims[name] == "name", name
        assert "using" not in claims and "costs" not in claims

    def test_the_first_word_of_a_line_is_not_a_name(self) -> None:
        assert extract_claims("Led a migration\nReporting for finance\nDashboards") == []

    def test_a_job_word_is_a_claim_only_if_the_job_asks_for_it(self) -> None:
        text = "improved kubernetes deployment reliability"
        assert extract_claims(text) == []
        assert ("kubernetes", "job term") in extract_claims(text, ["kubernetes", "terraform"])

    def test_job_vocabulary_drops_plain_words(self) -> None:
        words = job_vocabulary(
            ["Strong experience with Kubernetes and communication skills", "3 years"]
        )
        assert "kubernetes" in words and "communication" in words
        assert "experience" not in words and "3" not in words and "with" not in words


class TestVerify:
    BEFORE = [
        "Cut weekly reporting from two days to two hours with SQL",
        "Built a dashboard for 6 teams",
    ]
    EVIDENCE = [
        "Built a Tableau dashboard used by 6 teams at Kestrel Logistics",
        "Reduced report time by 90%",
    ]

    def verify(self, after: list[str], job: tuple[str, ...] = ()) -> Any:
        return verify_text(after, before=self.BEFORE, evidence=self.EVIDENCE, job_words=job)

    def test_rewording_what_is_already_true_passes(self) -> None:
        result = self.verify(
            [
                "Built a dashboard for 6 teams",
                "Cut weekly reporting from two days to two hours with SQL",
            ]
        )
        assert not result.blocked

    def test_a_fact_from_the_cited_evidence_passes_and_says_where_it_came_from(self) -> None:
        result = self.verify(["Built a Tableau dashboard for 6 teams at Kestrel Logistics"])
        assert not result.blocked
        sources = {c.text: c.source for c in result.claims}
        assert sources["tableau"] == "evidence" and sources["6"] == "resume"

    def test_an_invented_number_is_blocked(self) -> None:
        result = self.verify(["Built a dashboard for 60 teams"])
        assert result.blocked and [c.text for c in result.unsupported] == ["60"]

    def test_an_invented_tool_or_employer_is_blocked(self) -> None:
        result = self.verify(["Built a dashboard in Looker for Google"])
        assert {c.text for c in result.unsupported} == {"looker", "google"}

    def test_a_keyword_from_the_job_without_evidence_is_blocked(self) -> None:
        result = self.verify(["Built a dashboard and led kubernetes rollouts"], job=("kubernetes",))
        assert [c.text for c in result.unsupported] == ["kubernetes"]

    def test_a_number_is_matched_whole_not_as_a_piece_of_another(self) -> None:
        result = verify_text(["Saved 4 hours"], before=["Saved 40 hours"], evidence=[])
        assert result.blocked

    def test_commas_and_percent_signs_do_not_hide_a_number(self) -> None:
        ok = verify_text(
            ["Handled 1,200 rows, 90%"], before=["Handled 1200 rows and 90 percent"], evidence=[]
        )
        assert not ok.blocked

    def test_the_same_input_always_gives_the_same_answer(self) -> None:
        a = self.verify(["Built a dashboard in Looker"])
        b = self.verify(["Built a dashboard in Looker"])
        assert a == b


class TestCleanLines:
    def test_it_tidies_and_strips_bullet_marks(self) -> None:
        assert clean_lines(["  - Did   a  thing ", "• Another"]) == ["Did a thing", "Another"]

    @pytest.mark.parametrize("bad", [None, "text", [], [""], [5], ["x" * 301], ["a"] * 9])
    def test_unusable_input_is_refused(self, bad: Any) -> None:
        assert clean_lines(bad) is None
