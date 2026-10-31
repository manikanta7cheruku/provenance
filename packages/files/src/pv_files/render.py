"""Turn the resume HTML into a PDF.

The engine is WeasyPrint (ADR-0025, decided by a measured comparison with headless Chromium). It
runs in the worker, never in the API process. It is given an HTML string that this project built
from validated data (pv_domain.resume_render), with fonts read from the files shipped in this
package. It is told it may not fetch anything from the network: every URL it can see is a local
font file.
"""

import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from pv_domain.resume_render import FONT_FILES

# Font subsetting reports every table it touches at INFO. That is noise in the worker log.
for _noisy in ("fontTools", "weasyprint"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


class RenderError(Exception):
    """The PDF could not be made. The message never contains resume text."""


@dataclass(frozen=True)
class RenderedPdf:
    data: bytes
    page_count: int


def fonts_dir() -> Path:
    return Path(str(resources.files("pv_files").joinpath("assets", "fonts")))


def font_file(name: str) -> Path | None:
    """A shipped font file by name, or None. Only names the renderer uses are served."""
    if name not in FONT_FILES.values():
        return None
    path = fonts_dir() / name
    return path if path.is_file() else None


def _uri_to_path(url: str) -> Path:
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if len(path) > 2 and path[0] == "/" and path[2] == ":":  # a Windows drive path
        path = path[1:]
    return Path(path)


def _only_local_fonts(url: str, *_: Any, **__: Any) -> Any:
    """WeasyPrint's URL fetcher. It may read the shipped fonts and nothing else."""
    if urlparse(url).scheme != "file":
        raise ValueError("Only the shipped fonts may be loaded.")
    path = _uri_to_path(url).resolve()
    if path.parent != fonts_dir().resolve() or path.name not in FONT_FILES.values():
        raise ValueError("Only the shipped fonts may be loaded.")
    from weasyprint.urls import URLFetcherResponse

    return URLFetcherResponse(url, body=path.open("rb"), headers={"Content-Type": "font/woff"})


def html_to_pdf(html: str) -> RenderedPdf:
    from weasyprint import HTML  # imported here: it loads native libraries

    try:
        document = HTML(string=html, url_fetcher=_only_local_fonts).render()
        data = document.write_pdf()
    except Exception as exc:  # noqa: BLE001 - the library raises many kinds
        raise RenderError("The PDF could not be made.") from exc
    return RenderedPdf(data=data, page_count=len(document.pages))
