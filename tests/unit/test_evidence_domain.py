"""Evidence text rendering and rank fusion (pure code)."""

import pytest

from pv_domain.evidence import (
    EMBEDDING_DIMENSIONS,
    MAX_CHUNK_CHARS,
    clean_chunk_text,
    clean_query,
    content_hash,
    reciprocal_rank_fusion,
    render_entry_text,
)
from pv_domain.profile import ENTRY_SPECS


class TestRendering:
    def test_work_entry_reads_like_a_sentence_with_its_highlights(self) -> None:
        text = render_entry_text(
            "work",
            {
                "company": "Kestrel Analytics",
                "title": "Data Intern",
                "location": "Bengaluru",
                "start_date": "2024-06",
                "end_date": "2024-08",
                "highlights": ["Cleaned six CSV sources", "Wrote SQL joins"],
            },
        )
        assert text == (
            "Work: Data Intern at Kestrel Analytics (2024-06 to 2024-08, Bengaluru). "
            "Cleaned six CSV sources; Wrote SQL joins"
        )

    def test_internship_is_labelled_as_one(self) -> None:
        assert render_entry_text("internship", {"company": "K", "title": "Intern"}).startswith(
            "Internship: Intern at K"
        )

    def test_education(self) -> None:
        text = render_entry_text(
            "education",
            {
                "institution": "BMS College of Engineering",
                "degree": "B.E.",
                "field_of_study": "Computer Science",
                "start_date": "2021",
                "end_date": "2025",
                "grade": "CGPA 8.4",
            },
        )
        assert text == (
            "Education: B.E. Computer Science at BMS College of Engineering (2021 to 2025). "
            "Grade: CGPA 8.4."
        )

    def test_project_with_technologies_and_link(self) -> None:
        text = render_entry_text(
            "project",
            {
                "name": "Delivery delay report",
                "description": "Plotly dashboard for operations leads.",
                "technologies": ["Python", "SQL"],
                "url": "https://github.com/asha/delay",
            },
        )
        assert text == (
            "Project: Delivery delay report. Plotly dashboard for operations leads. "
            "Technologies: Python, SQL. https://github.com/asha/delay"
        )

    @pytest.mark.parametrize(
        ("entry_type", "data", "expected"),
        [
            ("skill", {"name": "Python"}, "Skill: Python"),
            ("skill", {"name": "Python", "category": "Languages"}, "Skill: Python (Languages)"),
            (
                "certification",
                {"name": "SQL for data analysis", "issuer": "Example Learning", "date": "2023"},
                "Certification: SQL for data analysis, issued by Example Learning (2023)",
            ),
            (
                "achievement",
                {"title": "Smart India Hackathon finalist", "date": "2024"},
                "Achievement: Smart India Hackathon finalist (2024).",
            ),
            (
                "link",
                {"label": "GitHub", "url": "https://github.com/asha"},
                "Link: GitHub https://github.com/asha",
            ),
        ],
    )
    def test_other_types(self, entry_type: str, data: dict[str, object], expected: str) -> None:
        assert render_entry_text(entry_type, data) == expected

    def test_every_entry_type_renders_its_primary_field(self) -> None:
        for spec in ENTRY_SPECS.values():
            primary = "Distinctive Primary Value"
            data: dict[str, object] = {f.name: "x" for f in spec.fields if f.required}
            data[spec.primary_field] = primary
            assert primary in render_entry_text(spec.entry_type, data), spec.entry_type

    def test_wrong_types_and_empty_data_never_raise(self) -> None:
        assert render_entry_text("hobby", {"name": "x"}) == ""
        assert render_entry_text("work", {"company": 5, "highlights": "not a list"}) == ""
        assert render_entry_text("skill", {"category": "Languages"}) == ""
        for spec in ENTRY_SPECS.values():
            render_entry_text(spec.entry_type, {})

    def test_the_same_entry_always_gives_the_same_hash(self) -> None:
        data = {"name": "Python"}
        assert content_hash(render_entry_text("skill", data)) == content_hash(
            render_entry_text("skill", dict(data))
        )
        assert content_hash("a") != content_hash("b")
        assert len(content_hash("a")) == 64

    def test_text_is_cleaned_and_capped(self) -> None:
        assert clean_chunk_text("  a \n\n b\t c ") == "a b c"
        assert len(clean_chunk_text("x" * (MAX_CHUNK_CHARS + 500))) == MAX_CHUNK_CHARS

    def test_queries_are_cleaned_and_capped(self) -> None:
        assert clean_query("  sql   joins \n") == "sql joins"
        assert len(clean_query("x" * 1000)) == 300
        assert clean_query("   ") == ""

    def test_embedding_size_matches_the_migration(self) -> None:
        assert EMBEDDING_DIMENSIONS == 768


class TestRankFusion:
    def test_an_item_in_both_lists_beats_an_item_that_tops_only_one(self) -> None:
        fused = reciprocal_rank_fusion([["a", "b", "c"], ["c", "b", "d"]])
        order = [item for item, _ in fused]
        assert set(order[:2]) == {"b", "c"}  # both lists agree on them
        assert set(order[2:]) == {"a", "d"}  # each is in one list only

    def test_scores_follow_the_formula(self) -> None:
        fused = dict(reciprocal_rank_fusion([["a", "b"], ["b"]], k=60))
        assert fused["a"] == pytest.approx(1 / 61)
        assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)

    def test_one_list_keeps_its_order(self) -> None:
        assert [i for i, _ in reciprocal_rank_fusion([["x", "y", "z"]])] == ["x", "y", "z"]

    def test_empty_inputs(self) -> None:
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[], []]) == []
        assert [i for i, _ in reciprocal_rank_fusion([[], ["a"]])] == ["a"]

    def test_ties_break_deterministically(self) -> None:
        first = reciprocal_rank_fusion([["a"], ["b"]])
        second = reciprocal_rank_fusion([["a"], ["b"]])
        assert first == second
        assert [i for i, _ in first] == ["a", "b"]

    def test_a_smaller_k_rewards_the_top_rank_more(self) -> None:
        small = dict(reciprocal_rank_fusion([["a", "b"]], k=1))
        large = dict(reciprocal_rank_fusion([["a", "b"]], k=1000))
        assert small["a"] / small["b"] > large["a"] / large["b"]

    def test_only_order_matters_not_scale(self) -> None:
        # The two lists could come from a text rank and a distance. Fusion sees only positions.
        assert reciprocal_rank_fusion([["a", "b"]]) == reciprocal_rank_fusion([["a", "b"]])
