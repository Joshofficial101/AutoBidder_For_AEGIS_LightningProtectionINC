"""
Bid calculation models for LightningBid system.

These classes represent the actual bid - materials needed, costs, and final pricing.
Think of this as the "shopping list" with prices attached.
"""

from pydantic import BaseModel
from typing import List, Optional
from src.models.items import PriceItem


class BidLineItem(BaseModel):
    """
    One line in the bid - a specific material or labor item.

    Example: "10 air terminals at $45 each = $450"
    """
    # Reference to the pricing item from Excel
    price_item: PriceItem

    # How many we need
    quantity: float

    # Total costs
    material_cost: float  # quantity × unit_price
    labor_cost: Optional[float] = None  # quantity × labor_rate (if applicable)

    # Why this item is needed (for reference)
    reason: Optional[str] = None  # e.g., "UL 96A: air terminals at roof corners"


class BidSection(BaseModel):
    """
    A section of the bid (e.g., Air Terminals, Conductors, Grounding).

    This helps organize the bid into logical groups.
    """
    name: str  # 'Air Terminals', 'Down Conductors', 'Grounding System', etc.
    line_items: List[BidLineItem] = []

    @property
    def total_material(self) -> float:
        """Sum of all material costs in this section."""
        return sum(item.material_cost for item in self.line_items)

    @property
    def total_labor(self) -> float:
        """Sum of all labor costs in this section."""
        return sum(item.labor_cost or 0 for item in self.line_items)

    @property
    def section_total(self) -> float:
        """Total cost for this section (material + labor)."""
        return self.total_material + self.total_labor


class Bid(BaseModel):
    """
    Complete bid for a lightning protection project.

    This is the final output that gets turned into Excel + PDF.
    """
    project_name: str

    # Organized sections of the bid
    sections: List[BidSection] = []

    # Markup percentages (configurable)
    material_markup_pct: float = 15.0  # 15% markup on materials
    labor_markup_pct: float = 20.0     # 20% markup on labor
    overhead_pct: float = 10.0         # 10% overhead
    profit_pct: float = 10.0           # 10% profit

    @property
    def subtotal_material(self) -> float:
        """Total material cost before markup."""
        return sum(section.total_material for section in self.sections)

    @property
    def subtotal_labor(self) -> float:
        """Total labor cost before markup."""
        return sum(section.total_labor for section in self.sections)

    @property
    def subtotal(self) -> float:
        """Total cost before markup."""
        return self.subtotal_material + self.subtotal_labor

    @property
    def total_with_markup(self) -> float:
        """Total after applying markup."""
        mat_markup = self.subtotal_material * (self.material_markup_pct / 100)
        lab_markup = self.subtotal_labor * (self.labor_markup_pct / 100)
        return self.subtotal + mat_markup + lab_markup

    @property
    def final_bid_amount(self) -> float:
        """Final bid amount including overhead and profit."""
        base = self.total_with_markup
        overhead = base * (self.overhead_pct / 100)
        profit = base * (self.profit_pct / 100)
        return base + overhead + profit
