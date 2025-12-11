"""
Enhanced Excel Loader for Lightning Protection Pricing Sheets

This module handles complex Excel formats including:
- Multiple sheets
- Variable header row positions
- Merged cells
- Different column name variations
- Missing or empty rows
"""

from pathlib import Path
import pandas as pd
import openpyxl
from typing import List, Optional, Dict, Tuple
from src.models.items import PriceItem


def _find_header_row(ws, max_rows_to_check: int = 20) -> Optional[int]:
    """
    Find the row that contains column headers.
    
    Looks for common header keywords in the first few rows.
    Returns 0-indexed row number (for pandas) or None if not found.
    """
    header_keywords = [
        "code", "item", "part", "description", "name", "price", "cost",
        "unit", "uom", "labor", "material", "type", "category"
    ]
    
    for row_idx in range(min(max_rows_to_check, ws.max_row)):
        row_values = [str(cell.value or "").lower().strip() for cell in ws[row_idx + 1]]
        # Check if this row contains multiple header keywords
        matches = sum(1 for val in row_values for keyword in header_keywords if keyword in val)
        if matches >= 3:  # Found at least 3 header keywords
            return row_idx
    
    return 0  # Default to first row


def _normalize_column_name(name: str) -> str:
    """Normalize column names for matching."""
    if pd.isna(name) or name is None:
        return ""
    return str(name).strip().lower().replace("_", " ").replace("-", " ")


def _map_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Map DataFrame columns to our expected fields.
    
    Returns a dictionary mapping field names to column names.
    """
    col_map = {}
    normalized_cols = {_normalize_column_name(col): col for col in df.columns}
    
    # Code/Part Number
    code_patterns = ["code", "item code", "part", "part #", "part number", "part no", "sku", "item number"]
    col_map["code"] = next((normalized_cols.get(pat) for pat in code_patterns if pat in normalized_cols), None)
    
    # Name/Description
    name_patterns = ["name", "description", "desc", "item", "material name", "product", "item name"]
    col_map["name"] = next((normalized_cols.get(pat) for pat in name_patterns if pat in normalized_cols), None)
    
    # Material Type
    type_patterns = ["type", "material type", "category", "cat", "material", "class"]
    col_map["material_type"] = next((normalized_cols.get(pat) for pat in type_patterns if pat in normalized_cols), None)
    
    # Unit
    unit_patterns = ["unit", "uom", "units", "unit of measure", "measure"]
    col_map["unit"] = next((normalized_cols.get(pat) for pat in unit_patterns if pat in normalized_cols), None)
    
    # Unit Price
    price_patterns = ["price", "unit price", "unit_cost", "cost", "unit cost", "price each", "each"]
    col_map["unit_price"] = next((normalized_cols.get(pat) for pat in price_patterns if pat in normalized_cols), None)
    
    # Labor Rate
    labor_patterns = ["labor", "labor rate", "labor_cost", "labor cost", "install", "installation", "labor each"]
    col_map["labor_rate"] = next((normalized_cols.get(pat) for pat in labor_patterns if pat in normalized_cols), None)
    
    return col_map


def _parse_price(value: any) -> Optional[float]:
    """Parse a price value from various formats."""
    if pd.isna(value) or value is None:
        return None
    
    try:
        # Convert to string and clean
        price_str = str(value).strip()
        if not price_str or price_str.lower() in ["nan", "none", "n/a", ""]:
            return None
        
        # Remove currency symbols and commas
        price_str = price_str.replace("$", "").replace(",", "").replace(" ", "")
        
        # Handle parentheses (negative values)
        if price_str.startswith("(") and price_str.endswith(")"):
            price_str = "-" + price_str[1:-1]
        
        return float(price_str)
    except (ValueError, AttributeError):
        return None


def _load_sheet(path: Path, sheet_name: Optional[str] = None, header_row: Optional[int] = None) -> pd.DataFrame:
    """
    Load a specific sheet from Excel file.
    
    Args:
        path: Path to Excel file
        sheet_name: Name of sheet to load (None = first sheet)
        header_row: Row index to use as header (None = auto-detect)
    
    Returns:
        DataFrame with data
    """
    # Use openpyxl to find header row if not specified
    if header_row is None:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        if sheet_name:
            ws = wb[sheet_name]
        else:
            ws = wb.active
        
        header_row = _find_header_row(ws)
        wb.close()
    
    # Load with pandas
    try:
        df = pd.read_excel(
            path,
            sheet_name=sheet_name,
            header=header_row,
            dtype=str,  # Read as strings first to avoid type issues
            na_values=["", "N/A", "n/a", "NULL", "null", "None"]
        )
        
        # Clean column names
        df.columns = [_normalize_column_name(col) for col in df.columns]
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        return df
    except Exception as e:
        raise ValueError(f"Error loading sheet '{sheet_name or 'default'}': {str(e)}")


def load_pricing_from_excel(path: Path, sheet_name: Optional[str] = None, 
                           try_all_sheets: bool = True) -> List[PriceItem]:
    """
    Load pricing items from Excel file.
    
    Enhanced version that handles:
    - Multiple sheets (tries all if sheet_name not specified)
    - Auto-detection of header rows
    - Merged cells (handled by openpyxl/pandas)
    - Various column name formats
    - Missing or empty rows
    
    Args:
        path: Path to Excel file
        sheet_name: Specific sheet name to load (None = try all sheets)
        try_all_sheets: If True and sheet_name is None, try all sheets until one works
    
    Returns:
        List of PriceItem objects
    
    Raises:
        ValueError: If file cannot be read or no valid data found
    """
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")
    
    all_items: List[PriceItem] = []
    sheets_tried = []
    
    # Get list of sheets to try
    if sheet_name:
        sheets_to_try = [sheet_name]
    elif try_all_sheets:
        try:
            wb = openpyxl.load_workbook(path, read_only=True)
            sheets_to_try = wb.sheetnames
            wb.close()
        except Exception:
            sheets_to_try = [None]  # Try default sheet
    else:
        sheets_to_try = [None]
    
    # Try each sheet
    for current_sheet in sheets_to_try:
        try:
            df = _load_sheet(path, sheet_name=current_sheet)
            sheets_tried.append(current_sheet or "default")
            
            if df.empty:
                continue
            
            # Map columns
            col_map = _map_columns(df)
            
            # Check for required columns
            missing = [k for k, v in col_map.items() if v is None and k in ("code", "name", "unit_price")]
            if missing:
                continue  # Try next sheet
            
            # Parse rows
            items = []
            for _, row in df.iterrows():
                # Skip if all key fields are empty
                if col_map["code"] and pd.isna(row.get(col_map["code"])):
                    continue
                if col_map["name"] and pd.isna(row.get(col_map["name"])):
                    continue
                
                # Parse price (required)
                unit_price = None
                if col_map["unit_price"]:
                    unit_price = _parse_price(row.get(col_map["unit_price"]))
                
                if unit_price is None:
                    continue  # Skip rows without valid price
                
                # Parse labor rate (optional)
                labor_rate = None
                if col_map["labor_rate"]:
                    labor_rate = _parse_price(row.get(col_map["labor_rate"]))
                
                # Extract other fields
                code = str(row.get(col_map["code"], "")).strip() if col_map["code"] else ""
                name = str(row.get(col_map["name"], "")).strip() if col_map["name"] else ""
                
                if not code and not name:
                    continue  # Skip rows with no identifier
                
                material_type = None
                if col_map["material_type"]:
                    val = row.get(col_map["material_type"])
                    if not pd.isna(val):
                        material_type = str(val).strip()
                
                unit = None
                if col_map["unit"]:
                    val = row.get(col_map["unit"])
                    if not pd.isna(val):
                        unit = str(val).strip()
                
                # Create PriceItem
                items.append(PriceItem(
                    code=code or f"ITEM-{len(items)+1}",
                    name=name or "Unnamed Item",
                    material_type=material_type if material_type else None,
                    unit=unit if unit else None,
                    unit_price=unit_price,
                    labor_rate=labor_rate
                ))
            
            if items:
                all_items.extend(items)
                # If we found items and sheet_name was specified, return immediately
                if sheet_name:
                    return all_items
        
        except Exception as e:
            # Log error but continue trying other sheets
            continue
    
    if not all_items:
        raise ValueError(
            f"Could not extract pricing data from {path.name}.\n"
            f"Tried sheets: {', '.join(sheets_tried)}\n"
            f"Please check that the Excel file has columns for: Code/Part, Name/Description, and Price."
        )
    
    return all_items