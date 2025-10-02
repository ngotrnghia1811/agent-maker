"""PDF utilities — split multi-page PDFs into single-page files.

Requires PyMuPDF (fitz).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_page_count(pdf_path: str | Path) -> int:
    """Return the number of pages in a PDF file."""
    import fitz

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    count = len(doc)
    doc.close()
    return count


def split_pdf_to_pages(
    pdf_path: str | Path,
    output_dir: str | Path,
    page_prefix: str = "page",
) -> list[Path]:
    """Split a multi-page PDF into individual single-page PDF files.

    Args:
        pdf_path: Path to the source PDF.
        output_dir: Directory to write individual page PDFs.
        page_prefix: Filename prefix for each page (e.g., "page" → page_001.pdf).

    Returns:
        Sorted list of paths to the generated single-page PDFs.
    """
    import fitz

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    page_paths: list[Path] = []

    width = len(str(total_pages))  # zero-pad width

    for page_num in range(total_pages):
        page_filename = f"{page_prefix}_{str(page_num + 1).zfill(width)}.pdf"
        page_path = output_dir / page_filename

        single_doc = fitz.open()  # new empty document
        single_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
        single_doc.save(str(page_path))
        single_doc.close()

        page_paths.append(page_path)
        logger.debug("Extracted page %d/%d → %s", page_num + 1, total_pages, page_path.name)

    doc.close()
    logger.info("Split %s into %d pages → %s", pdf_path.name, total_pages, output_dir)

    return page_paths
