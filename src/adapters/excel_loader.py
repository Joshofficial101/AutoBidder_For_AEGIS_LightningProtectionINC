from pathlib import Path
import pandas as pd
from typing import List
from src.models.items import PriceItem

def load_pricing_from_excel(path: Path) -> List[PriceItem]:
    # Try first sheet by default; adjust sheet_name= if you know the exact tab
    df = pd.read_excel(path, dtype=str)  # read all as str to avoid weirdness
    df.columns = [c.strip().lower() for c in df.columns]

    # Try to map likely column names (robust to different headers)
    col_map = {
        "code": next((c for c in df.columns if c in ["code", "item code", "part", "part #", "part number"]), None),
        "name": next((c for c in df.columns if c in ["name", "description", "item", "material name"]), None),
        "material_type": next((c for c in df.columns if c in ["type", "material type", "category"]), None),
        "unit": next((c for c in df.columns if c in ["unit", "uom", "units"]), None),
        "unit_price": next((c for c in df.columns if c in ["price", "unit price", "unit_cost", "cost"]), None),
        "labor_rate": next((c for c in df.columns if c in ["labor", "labor rate", "labor_cost"]), None),
    }

    missing = [k for k, v in col_map.items() if v is None and k in ("code", "name", "unit_price")]
    if missing:
        raise ValueError(f"Missing required columns in {path.name}: {missing}\nFound columns: {list(df.columns)}")

    items: List[PriceItem] = []
    for _, row in df.iterrows():
        try:
            unit_price = float(str(row[col_map["unit_price"]]).replace("$","").replace(",","").strip())
        except Exception:
            continue  # skip rows that aren't price rows

        items.append(PriceItem(
            code=(row[col_map["code"]] if col_map["code"] else "").strip(),
            name=(row[col_map["name"]] if col_map["name"] else "").strip(),
            material_type=(row[col_map["material_type"]] if col_map["material_type"] else None),
            unit=(row[col_map["unit"]] if col_map["unit"] else None),
            unit_price=unit_price,
            labor_rate=float(str(row[col_map["labor_rate"]]).replace("$","").replace(",","").strip()) if col_map["labor_rate"] and str(row[col_map["labor_rate"]]).strip() not in ("", "nan", "None") else None
        ))
    return items