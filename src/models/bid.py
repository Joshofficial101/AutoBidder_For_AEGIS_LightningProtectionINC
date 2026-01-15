"""
Bid calculation models for LightningBid system.

These classes represent the actual bid - materials needed, costs, and final pricing.
Think of this as the "shopping list" with prices attached.
"""

from pydantic import BaseModel, Field
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
    line_items: List[BidLineItem] = Field(default_factory=list)

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
    sections: List[BidSection] = Field(default_factory=list)

    # Markup percentages (configurable)
    material_markup_pct: float = 0.0   # No markup - LIST PRICE already includes markup
    labor_markup_pct: float = 20.0     # 20% markup on labor
    overhead_pct: float = 10.0         # 10% overhead
    profit_pct: float = 10.0           # 10% profit
    
    # Additional flat costs (configurable)
    commission_amount: float = 0.0     # Commission (flat dollar amount)
    tools_rental_amount: float = 0.0   # Tools & rental (amount)
    tools_rental_type: str = "$"       # Tools & rental type: "$" (flat) or "%" (percentage)
    shipping_amount: float = 0.0       # Shipping cost (flat dollar amount)
    use_tax_pct: float = 0.0           # Use tax percentage (applied to materials + shipping only)

    @property
    def subtotal_material(self) -> float:
        """Total material cost before markup."""
        return sum(section.total_material for section in self.sections)

    @property
    def subtotal_labor(self) -> float:
        """Total labor cost before markup."""
        return sum(section.total_labor for section in self.sections)

    @property
    def material_with_shipping(self) -> float:
        """Material cost + shipping (before tax)."""
        return self.subtotal_material + self.shipping_amount
    
    @property
    def material_tax(self) -> float:
        """Use tax applied to materials + shipping."""
        return self.material_with_shipping * (self.use_tax_pct / 100)
    
    @property
    def material_total_with_tax(self) -> float:
        """Material + shipping + tax."""
        return self.material_with_shipping + self.material_tax
    
    @property
    def subtotal(self) -> float:
        """Total cost before markup (includes material + shipping + tax + labor)."""
        return self.material_total_with_tax + self.subtotal_labor

    @property
    def total_with_markup(self) -> float:
        """Total after applying markup (material already has tax, only labor gets markup)."""
        # Material already has shipping and tax applied, no additional markup
        mat_markup = self.subtotal_material * (self.material_markup_pct / 100)
        lab_markup = self.subtotal_labor * (self.labor_markup_pct / 100)
        return self.subtotal + mat_markup + lab_markup

    @property
    def tools_rental_cost(self) -> float:
        """Calculate tools/rental cost based on type ($ flat or % of subtotal)."""
        if self.tools_rental_type == "%":
            return self.subtotal * (self.tools_rental_amount / 100)
        else:  # "$" flat amount
            return self.tools_rental_amount
    
    @property
    def final_bid_amount(self) -> float:
        """Final bid amount including overhead, profit, and additional costs."""
        base_with_markup = self.total_with_markup
        # Apply overhead & profit to ORIGINAL subtotal (which now includes tax), not marked-up amount
        overhead = self.subtotal * (self.overhead_pct / 100)
        profit = self.subtotal * (self.profit_pct / 100)
        # Add flat/percentage additional costs
        return base_with_markup + overhead + profit + self.commission_amount + self.tools_rental_cost
