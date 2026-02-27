from pathlib import Path
import sys
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.pdf_loader import parse_pdf_flexible
from app.file_limits import assert_pdf_file_within_limit


def parse_pdf(pdf_file_path: str) -> Dict[str, Any]:
    if not pdf_file_path:
        raise ValueError("pdf_file_path is required")

    path_obj = Path(pdf_file_path)
    if not path_obj.exists():
        raise ValueError("pdf_file_path does not exist")
    assert_pdf_file_within_limit(path_obj)

    return parse_pdf_flexible(path_obj)
