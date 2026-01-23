import pdfplumber
from pathlib import Path
import time

pdf_path = Path("data/inputs/BC23-001053 Electrical Building Plans (General Building) - APPROVED.pdf")

print(f"Testing PDF: {pdf_path.name}")
print(f"File size: {pdf_path.stat().st_size / (1024*1024):.2f} MB")

try:
    start = time.time()
    with pdfplumber.open(pdf_path) as pdf:
        open_time = time.time() - start
        print(f"Time to open: {open_time:.2f} seconds")
        print(f"Total pages: {len(pdf.pages)}")
        
        # Try extracting text from just page 1
        start = time.time()
        text = pdf.pages[0].extract_text() or ""
        extract_time = time.time() - start
        
        print(f"Time to extract page 1: {extract_time:.2f} seconds")
        print(f"Text length: {len(text)} chars")
        print(f"Sample text: {text[:200]}")
        
except Exception as e:
    print(f"Error: {e}")
