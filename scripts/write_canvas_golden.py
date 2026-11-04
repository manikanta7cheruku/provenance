"""Write the CSS golden file that the server and the browser both have to match.

    uv run python scripts/write_canvas_golden.py

Run it only when the canvas CSS is changed on purpose. Then update css.ts in the studio canvas
folder until its test passes against the new file.
"""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "tests"))
sys.path.insert(0, str(root / "tests" / "unit"))

from test_resume_canvas import (  # noqa: E402
    GOLDEN,
    ICONS_GOLDEN,
    TestSharedCss,
    build_icons_golden,
)


def main() -> None:
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(TestSharedCss().build(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {GOLDEN.relative_to(root)}")
    ICONS_GOLDEN.write_text(json.dumps(build_icons_golden(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {ICONS_GOLDEN.relative_to(root)}")


if __name__ == "__main__":
    main()
