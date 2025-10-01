from pathlib import Path
import pdfplumber
from typing import Dict, List

KEY_SECTIONS = ["PART 1", "PART 2", "PART 3", "SUBMITTALS", "INSTALLATION", "GROUNDING", "AIR TERMINALS", "CONDUCTORS"]

KEY_TERMS = [
    "UL 96A", "NFPA 780", "air terminal", "downlead", "ground rod",
    "bonding", "conductor", "aluminum", "copper", "bimetal", "two-way path",
    "intervals", "20 feet", "25 feet", "50 feet", "100'", "bending radius", "8 inches"
]

def extract_spec_terms(path: Path) -> Dict[str, List[str]]:
    hits: Dict[str, List[str]] = {k: [] for k in KEY_SECTIONS + KEY_TERMS}
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            t_low = text.lower()

            # Section hits by header presence
            for sec in KEY_SECTIONS:
                if sec.lower() in t_low:
                    hits[sec].append(f"p{i}")

            # Keyword hits
            for term in KEY_TERMS:
                if term.lower() in t_low:
                    hits[term].append(f"p{i}")
    # remove keys with no hits
    return {k: v for k, v in hits.items() if v}
