from pydantic import BaseModel
from typing import Optional

class PriceItem(BaseModel):
    code: str
    name: str
    material_type: Optional[str] = None
    unit: Optional[str] = None
    unit_price: float
    labor_rate: Optional[float] = None