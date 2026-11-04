"""Pictures and icons on the canvas: what is accepted, who may use which picture, and how they are drawn."""

import re
from typing import Any

import pytest
from canvas_helpers import IMAGE_ID, canvas, icon_el, image_el, rich, shape_el, text_el
from defusedxml import ElementTree

from pv_domain.resume_canvas import (
    MAX_ELEMENTS,
    canvas_text,
    image_ids,
    paint_order,
    raw_image_ids,
    reading_order,
    render_canvas_html,
    validate_canvas,
)
from pv_domain.resume_doc import ResumeDocError
from pv_domain.resume_icons import ICON_DATA, ICON_LABELS, ICON_NAMES, WEIGHTS, icon_svg
from pv_domain.resume_images import MAX_IMAGES_PER_DOCUMENT, ImageBlob, ImageInfo

MINE = {IMAGE_ID: ImageInfo(IMAGE_ID, 800, 1000, "image/jpeg")}
OTHER_ID = "9a8b7c6d-1111-4222-8333-444455556666"
BLOB = {IMAGE_ID: ImageBlob("image/jpeg", b"\xff\xd8\xff\xd9")}
FONT = "file:///fonts/"


def problems_of(raw: Any, images: Any = MINE) -> dict[str, str]:
    with pytest.raises(ResumeDocError) as error:
        validate_canvas(raw, images)
    return error.value.problems


def clean(*elements: dict[str, Any], images: Any = MINE) -> dict[str, Any]:
    return validate_canvas(canvas(*elements), images)


def html(doc: dict[str, Any], blobs: Any = BLOB) -> str:
    return render_canvas_html(doc, font_base=FONT, blobs=blobs)


# --------------------------------------------------------------------- whose picture


def test_a_picture_the_person_owns_is_accepted_and_kept_as_it_is() -> None:
    doc = clean(image_el("i", 150, 12, 40, 50))
    el = doc["pages"][0]["elements"][0]
    assert (el["kind"], el["image_id"], el["fit"], el["shape"]) == (
        "image",
        IMAGE_ID,
        "cover",
        "rect",
    )
    assert image_ids(doc) == {IMAGE_ID}


def test_a_picture_that_is_not_the_persons_is_refused_in_the_same_words_as_a_deleted_one() -> None:
    stranger = problems_of(canvas(image_el("i", 10, 10, 20, 20, image_id=OTHER_ID)))
    deleted = problems_of(canvas(image_el("i", 10, 10, 20, 20)), images={})
    assert stranger["pages.0.elements.0.image_id"] == deleted["pages.0.elements.0.image_id"]
    assert "not available" in stranger["pages.0.elements.0.image_id"]


def test_with_no_pictures_to_check_against_a_picture_is_never_trusted() -> None:
    assert "pages.0.elements.0.image_id" in problems_of(
        canvas(image_el("i", 10, 10, 20, 20)), images=None
    )


@pytest.mark.parametrize(
    "bad", ["", "not an id", "../../etc/passwd", "x" * 80, None, 5, ["a"], {"a": 1}]
)
def test_a_picture_id_that_is_not_an_id_is_refused(bad: Any) -> None:
    assert "pages.0.elements.0.image_id" in problems_of(
        canvas(image_el("i", 10, 10, 20, 20, image_id=bad))
    )


def test_the_ids_a_request_claims_are_read_without_trusting_it() -> None:
    raw = canvas(
        image_el("i", 10, 10, 20, 20),
        image_el("j", 10, 40, 20, 20, image_id=OTHER_ID),
        shape_el("s", 1, 1, 5, 5),
    )
    assert raw_image_ids(raw) == {IMAGE_ID, OTHER_ID}
    for garbage in (
        None,
        5,
        "x",
        [],
        {"pages": 5},
        {"pages": [5, None, {"elements": 3}]},
        {"pages": [{"elements": [{"kind": "image", "image_id": 7}]}]},
    ):
        assert raw_image_ids(garbage) == set()


# --------------------------------------------------------------------- the picture's own settings


def test_fit_shape_crop_and_outline_are_checked() -> None:
    bad = image_el(
        "i",
        10,
        10,
        30,
        30,
        fit="stretch",
        shape="star",
        focus_x=150,
        focus_y=-5,
        border="pink",
        border_pt=99,
    )
    keys = set(problems_of(canvas(bad)))
    assert {
        f"pages.0.elements.0.{k}"
        for k in ("fit", "shape", "focus_x", "focus_y", "border", "border_pt")
    } <= keys


def test_the_alt_text_is_tidied_and_cut_and_a_picture_may_be_marked_decorative() -> None:
    el = clean(image_el("i", 10, 10, 30, 30, alt="  A   photo\x00 " + "x" * 400, decorative=True))[
        "pages"
    ][0]["elements"][0]
    assert el["alt"].startswith("A photo x") and len(el["alt"]) == 200 and el["decorative"] is True


def test_a_picture_must_fit_on_the_page_like_any_box() -> None:
    assert "pages.0.elements.0.w" in problems_of(canvas(image_el("i", 190, 10, 40, 30)))
    assert "pages.0.elements.0.h" in problems_of(canvas(image_el("i", 10, 280, 30, 40)))


def test_a_resume_may_hold_only_a_few_pictures() -> None:
    many = [image_el(f"i{n}", 5 + 12 * n, 5, 10, 10) for n in range(MAX_IMAGES_PER_DOCUMENT + 1)]
    assert "pages" in problems_of(canvas(*many))
    assert (
        len(clean(*many[:MAX_IMAGES_PER_DOCUMENT])["pages"][0]["elements"])
        == MAX_IMAGES_PER_DOCUMENT
    )


# --------------------------------------------------------------------- icons


def test_every_icon_is_accepted_and_an_unknown_one_is_refused() -> None:
    for n, name in enumerate(ICON_NAMES):
        assert (
            clean(icon_el(f"c{n}", 10, 10, 5, 5, icon=name))["pages"][0]["elements"][0]["icon"]
            == name
        )
    assert "pages.0.elements.0.icon" in problems_of(
        canvas(icon_el("c", 10, 10, 5, 5, icon="skull"))
    )
    assert "pages.0.elements.0.icon" in problems_of(
        canvas(icon_el("c", 10, 10, 5, 5, icon="<script>"))
    )


def test_icon_weight_color_and_label_are_checked() -> None:
    bad = icon_el("c", 10, 10, 5, 5, weight=9, color="red")
    assert {"pages.0.elements.0.weight", "pages.0.elements.0.color"} <= set(
        problems_of(canvas(bad))
    )
    assert "pages.0.elements.0.weight" in problems_of(
        canvas(icon_el("c", 10, 10, 5, 5, weight=True))
    )
    label = clean(icon_el("c", 10, 10, 5, 5, alt="x" * 300))["pages"][0]["elements"][0]["alt"]
    assert len(label) == 80


def test_the_icons_are_valid_and_use_only_plain_drawing_shapes() -> None:
    assert set(ICON_NAMES) == set(ICON_LABELS) and len(ICON_NAMES) >= 12
    for name in ICON_NAMES:
        for weight in WEIGHTS:
            root = ElementTree.fromstring(icon_svg(name, weight))
            tags = {el.tag.split("}")[-1] for el in root.iter()}
            assert tags <= {"svg", "path", "circle", "rect", "polyline"}, (name, tags)
            assert not [
                a
                for el in root.iter()
                for a in el.attrib
                if a.lower().startswith("on") or a in ("href", "style")
            ]
    assert all(
        s["t"] in ("path", "circle", "rect", "polyline")
        for shapes in ICON_DATA.values()
        for s in shapes
    )


def test_no_icon_names_a_brand() -> None:
    brands = {"linkedin", "github", "twitter", "facebook", "instagram", "google", "indeed"}
    assert not brands & set(ICON_NAMES)


# --------------------------------------------------------------------- drawing


def test_a_picture_is_drawn_from_its_own_bytes_with_nothing_fetched() -> None:
    page = html(clean(image_el("i", 150, 12, 40, 50, alt='A "photo" <b>of</b> Asha')))
    assert 'src="data:image/jpeg;base64,/9j/2Q=="' in page
    assert 'alt="A &quot;photo&quot; &lt;b&gt;of&lt;/b&gt; Asha"' in page  # escaped, never markup
    assert "<b>of</b>" not in page
    assert not re.search(r'(src|href)="https?:', page)


def test_a_decorative_picture_has_empty_alt_text() -> None:
    page = html(clean(image_el("i", 150, 12, 40, 50, decorative=True)))
    assert 'alt=""' in page and "A photo of the applicant" not in page


def test_a_picture_whose_file_is_missing_draws_an_empty_box_not_an_error() -> None:
    page = html(clean(image_el("i", 150, 12, 40, 50)), blobs={})
    assert "<img" not in page and 'class="el"' in page


def test_the_box_is_clipped_and_shaped_and_the_picture_fills_it() -> None:
    page = html(
        clean(
            image_el(
                "i",
                20,
                20,
                30,
                30,
                shape="circle",
                fit="contain",
                focus_x=25,
                focus_y=75,
                border="accent",
                border_pt=1.5,
            )
        )
    )
    assert (
        "overflow:hidden" in page
        and "border-radius:50%" in page
        and "border:1.5pt solid #1f3d7a" in page
    )
    assert "object-fit:contain" in page and "object-position:25% 75%" in page


def test_an_icon_is_hidden_from_assistive_technology_unless_it_has_a_label() -> None:
    plain = html(clean(icon_el("c", 16, 40, 4, 4)))
    assert 'aria-hidden="true"' in plain and "<svg" in plain and "currentColor" in plain
    labelled = html(clean(icon_el("c", 16, 40, 4, 4, alt='Email "me"')))
    assert 'role="img"' in labelled and 'aria-label="Email &quot;me&quot;"' in labelled


def test_an_icon_takes_its_color_from_the_style() -> None:
    page = html(clean(icon_el("c", 16, 40, 4, 4, color="accent")))
    assert "color:#1f3d7a" in page


def test_pictures_and_icons_add_no_text_and_do_not_change_reading_order() -> None:
    doc = clean(
        text_el("name", 16, 16, 100, 8, rich("Asha Rao")),
        image_el("photo", 150, 10, 40, 50),
        icon_el("mail", 16, 30, 4, 4),
        text_el("line", 22, 30, 100, 5, rich("asha@example.com")),
    )
    assert canvas_text(doc) == "Asha Rao\nasha@example.com"
    names = [e["name"] for e in reading_order(doc["pages"][0]["elements"])]
    assert names.index("name") < names.index("mail") < names.index("line")
    assert len(paint_order(doc["pages"][0]["elements"])) == 4


def test_a_picture_can_sit_under_text_and_stacking_is_kept() -> None:
    doc = clean(image_el("back", 10, 10, 100, 40), text_el("over", 20, 20, 60, 8, rich("On top")))
    order = [e["name"] for e in paint_order(doc["pages"][0]["elements"])]
    assert order == ["back", "over"]


def test_the_total_number_of_elements_still_counts_pictures_and_icons() -> None:
    icons = [
        icon_el(f"c{n}", 5 + (n % 20) * 9, 5 + (n // 20) * 9, 5, 5) for n in range(MAX_ELEMENTS + 1)
    ]
    assert "pages" in problems_of(canvas(*icons))
