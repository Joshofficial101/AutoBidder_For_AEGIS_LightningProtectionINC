import pdfplumber
from pathlib import Path
import re

pdf_path = Path("data/inputs/BC23-001053 Electrical Building Plans (General Building) - APPROVED.pdf")

print("Extracting ONLY page 1 for dimensions...")

with pdfplumber.open(pdf_path) as pdf:
    text = pdf.pages[0].extract_text() or ""
    
    print(f"\n--- Full Page 1 Text ---\n{text}\n")
    
    # Look for dimensions
    print("\n--- Searching for dimensions ---")
    
    # Pattern: Length x Width
    lxw_matches = re.findall(r'(\d+)[\'"\s-]*[xX×][\s-]*(\d+)[\'"\s]*', text)
    if lxw_matches:
        print(f"Found LxW patterns: {lxw_matches}")
    
    # Pattern: Area
    area_matches = re.findall(r'(\d+[,\d]*)\s*(?:sq\.?\s*ft|square\s+feet|sf)', text, re.IGNORECASE)
    if area_matches:
        print(f"Found area: {area_matches}")
    
    # Pattern: Height
    height_matches = re.findall(r'(?:height|tall)[:\s]+(\d+)', text, re.IGNORECASE)
    if height_matches:
        print(f"Found height: {height_matches}")
