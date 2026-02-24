# Advanced CAD PDF Parser - User Guide

## What Was Fixed

The PDF parser now **automatically detects** CAD-style building plans and uses **OCR + Computer Vision** to extract dimensions from drawings.

### Before:
- ❌ Could only read text-based specification documents
- ❌ CAD drawings with minimal text failed to parse
- ❌ No dimension extraction from visual drawings

### After:
- ✅ Auto-detects CAD drawings vs spec documents
- ✅ Uses OCR to read dimension callouts from drawings
- ✅ Computer vision analyzes building layouts
- ✅ Extracts: Length, Width, Height, Area, Perimeter

---

## How to Use

### In the GUI:

1. **Start the app:**
   ```bash
   run_desktop.cmd
   ```

2. **Click "📄 Search PDF"** to select your building plan PDF

3. **Wait for parsing** (may take 10-30 seconds for CAD drawings)
   - A progress bar will appear at the top
   - OCR processing happens in the background
   - **Console output shows progress** (check terminal window)

4. **Fields auto-populate** with extracted data:
   - Building Height
   - Roof Area
   - Perimeter
   - Length × Width (calculated)

### What to Expect:

**For CAD Building Plans** (like BC23-001053):
```
Detected CAD-style building plan. Using advanced OCR/CV parser...
[1/4] Extracting text content... [OK]
[2/4] Performing OCR on drawings... [OK] 
[3/4] Performing computer vision analysis... [OK]
[4/4] Parsing project information... [OK]
Found dimensions: L=480.0, W=400.0, H=None
```

**For Text Spec Documents**:
```
Using standard text-based parser...
```

---

## Troubleshooting

### "PDF parsing is taking forever"

**Cause:** OCR processing is intensive, especially on large PDFs

**Solutions:**
1. **Check the terminal/console** - You should see progress messages
2. **Wait 30-60 seconds** - First parse of a CAD drawing takes time
3. **Smaller PDFs process faster** - 16-page CAD plans take ~30 seconds

### "No dimensions extracted"

**Possible causes:**
1. **Dimension callouts are too small** - OCR can't read tiny text
2. **Non-standard format** - Dimensions in tables/schedules (not callouts)
3. **Image quality poor** - Scanned/blurry PDFs harder to read

**Solutions:**
1. Try a higher-quality PDF if available
2. Manually enter dimensions if extraction fails
3. Check console for "Warning: No dimensions extracted" message

### "Fields not populating"

**Check:**
1. **Is the GUI frozen?** - Check if progress bar is moving
2. **Check console/terminal** - Look for error messages
3. **PDF file selected?** - Make sure file path is shown
4. **Restart GUI** - Close and reopen if it seems stuck

---

## Installed Components

The following were installed for advanced PDF parsing:

### Python Libraries:
- `pdf2image` - Convert PDF pages to images
- `pytesseract` - OCR text extraction
- `opencv-python` - Computer vision for line/shape detection
- `Pillow` - Image processing
- `numpy` - Array operations for CV

### External Tools:
- **Poppler** (v24.08.0) - PDF rendering
  - Location: `C:\Users\Skyhi\PycharmProjects\PythonProject\poppler\`
  - Auto-configured in parser

- **Tesseract-OCR** (v5.4.0) - Text recognition
  - Location: `C:\Program Files\Tesseract-OCR\`
  - Auto-detected by parser

---

## Performance Notes

### Parsing Times (Approximate):

| PDF Type | Pages | Time |
|----------|-------|------|
| Text spec document | 5-10 | 1-3 sec |
| CAD building plan (first time) | 10-20 | 20-40 sec |
| CAD building plan (cached) | 10-20 | 5-10 sec |

### Why OCR Takes Time:
1. **PDF → Image conversion** (high DPI for quality)
2. **OCR processing** (analyzing each page)
3. **Computer vision** (detecting lines, shapes)
4. **Pattern matching** (finding dimension callouts)

---

## Technical Details

### Auto-Detection Logic:
```python
# If average text per page < 1000 chars → CAD drawing
# Use advanced OCR/CV parser
# Otherwise → Use standard text parser
```

### Extraction Strategy:
1. **Text extraction** (pdfplumber) - Fast, works for text PDFs
2. **OCR extraction** (pytesseract) - Reads dimension callouts from images
3. **Computer vision** (opencv) - Detects building outlines, lines
4. **Pattern matching** - Identifies dimension formats (40'-0", 60x80, etc.)
5. **Validation** - Filters to reasonable building dimensions (10-500 ft)

---

## Next Steps

If you need to:
- **Improve extraction accuracy** - We can tune OCR settings
- **Add height detection** - Currently not extracting building height from CAD plans
- **Support more formats** - Add patterns for other dimension notations
- **Speed up processing** - Could reduce DPI or limit pages scanned

Let me know what else you need!
