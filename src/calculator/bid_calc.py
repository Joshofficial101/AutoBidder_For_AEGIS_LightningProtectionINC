"""
Bid Calculator - The Brain of LightningBid

This module takes:
1. Compliance requirements (from UL 96A / NFPA 780)
2. Pricing data (from Excel sheets)

And produces:
- A complete bid with quantities and costs

Think of this as the "translator" that converts engineering requirements
into a shopping list with prices.
"""

from typing import List, Dict, Any, Optional
from src.models.items import PriceItem
from src.models.bid import Bid, BidSection, BidLineItem
from src.compliance.ul96a import UL96ACompliance
from src.compliance.nfpa780 import NFPA780Compliance


class BidCalculator:
    """
    Main bid calculation engine.

    This class maps compliance requirements to pricing items and
    generates a complete bid.
    """

    def __init__(self, price_catalog: List[PriceItem], compliance_code: str = "UL 96A"):
        """
        Initialize calculator with pricing catalog.

        Args:
            price_catalog: List of PriceItem objects from Excel
            compliance_code: Which code to use ('UL 96A' or 'NFPA 780')
        """
        self.price_catalog = price_catalog
        self.compliance_code = compliance_code

        # Build a quick lookup dictionary for finding items by keywords
        self._build_item_index()

    def _build_item_index(self):
        """
        Create searchable index of price items.

        This helps us quickly find items like "air terminal" or "ground rod"
        from the pricing sheet.
        """
        self.item_index: Dict[str, List[PriceItem]] = {}

        # Common keywords to index
        keywords = [
            "air terminal", "lightning rod", "terminal",
            "conductor", "cable", "wire", "downlead",
            "ground rod", "grounding", "electrode",
            "bonding", "clamp", "connector",
            "labor", "installation"
        ]

        for keyword in keywords:
            self.item_index[keyword] = []
            for item in self.price_catalog:
                # Check if keyword appears in item name or code
                if keyword.lower() in item.name.lower() or keyword.lower() in item.code.lower():
                    self.item_index[keyword].append(item)

    def find_item(self, search_term: str, prefer_material: Optional[str] = None) -> Optional[PriceItem]:
        """
        Find a price item by search term.

        Args:
            search_term: What to search for (e.g., "air terminal")
            prefer_material: Preferred material type (e.g., "copper", "aluminum")

        Returns:
            Best matching PriceItem or None
        """
        candidates = self.item_index.get(search_term.lower(), [])

        if not candidates:
            # Fallback: search all items
            for item in self.price_catalog:
                if search_term.lower() in item.name.lower():
                    candidates.append(item)

        if not candidates:
            return None

        # If material preference specified, filter
        if prefer_material:
            filtered = [item for item in candidates if prefer_material.lower() in (item.material_type or "").lower()]
            if filtered:
                candidates = filtered

        # Return first match (or most relevant)
        return candidates[0]

    def calculate_bid(self, project_data: Dict[str, Any]) -> Bid:
        """
        Main method: Calculate complete bid for a project.

        Args:
            project_data: Dictionary with project specs:
                - project_name: str
                - building_height_ft: float
                - roof_area_sqft: float
                - num_corners: int
                - perimeter_ft: float (optional)
                - soil_type: str (optional)
                - has_metal_roof: bool (optional)
                - preferred_material: str (optional, 'copper' or 'aluminum')

        Returns:
            Complete Bid object with all sections and line items
        """
        # Step 1: Get compliance requirements
        if self.compliance_code == "UL 96A":
            compliance = UL96ACompliance.check_compliance(project_data)
        else:  # NFPA 780
            compliance = NFPA780Compliance.check_compliance(project_data)

        # Step 2: Create bid object
        bid = Bid(project_name=project_data.get("project_name", "Lightning Protection Bid"))

        # Step 3: Build each section
        preferred_material = project_data.get("preferred_material", "copper")

        # Section 1: Air Terminals
        if "air_terminals" in compliance:
            air_terminal_section = self._build_air_terminal_section(
                compliance["air_terminals"],
                preferred_material
            )
            bid.sections.append(air_terminal_section)

        # Section 2: Conductors
        if "conductors" in compliance:
            conductor_section = self._build_conductor_section(
                compliance["conductors"],
                preferred_material
            )
            bid.sections.append(conductor_section)

        # Section 3: Grounding
        if "grounding" in compliance:
            grounding_section = self._build_grounding_section(
                compliance["grounding"]
            )
            bid.sections.append(grounding_section)

        # Section 4: Bonding (NFPA 780 specific)
        if "bonding" in compliance and compliance["bonding"]["total_connections"] > 0:
            bonding_section = self._build_bonding_section(
                compliance["bonding"],
                preferred_material
            )
            bid.sections.append(bonding_section)

        return bid

    def _build_air_terminal_section(self, requirements: Dict[str, Any], material: str) -> BidSection:
        """Build the Air Terminals section of the bid."""
        section = BidSection(name="Air Terminals")

        quantity = requirements["total"]

        # Find air terminal item from catalog
        item = self.find_item("air terminal", prefer_material=material)
        if not item:
            item = self.find_item("terminal")  # fallback

        if item:
            material_cost = quantity * item.unit_price
            labor_cost = (quantity * item.labor_rate) if item.labor_rate else (quantity * 15)  # $15 default labor per terminal

            line_item = BidLineItem(
                price_item=item,
                quantity=quantity,
                material_cost=material_cost,
                labor_cost=labor_cost,
                reason=requirements.get("notes", "Lightning protection air terminals")
            )
            section.line_items.append(line_item)

        return section

    def _build_conductor_section(self, requirements: Dict[str, Any], material: str) -> BidSection:
        """Build the Conductors section of the bid."""
        section = BidSection(name="Down Conductors & Main Cables")

        total_length = requirements["total_length_ft"]

        # Find conductor cable
        item = self.find_item("conductor", prefer_material=material)
        if not item:
            item = self.find_item("cable", prefer_material=material)

        if item:
            # Cable typically priced per foot
            material_cost = total_length * item.unit_price
            labor_cost = (total_length * item.labor_rate) if item.labor_rate else (total_length * 2)  # $2/ft default labor

            line_item = BidLineItem(
                price_item=item,
                quantity=total_length,
                material_cost=material_cost,
                labor_cost=labor_cost,
                reason=requirements.get("notes", "Lightning conductor cables")
            )
            section.line_items.append(line_item)

        # Add fasteners/supports (every 3 ft)
        supports_needed = int(total_length / 3)
        support_item = self.find_item("clamp")
        if not support_item:
            support_item = self.find_item("connector")

        if support_item:
            material_cost = supports_needed * support_item.unit_price
            labor_cost = (supports_needed * support_item.labor_rate) if support_item.labor_rate else (supports_needed * 5)

            line_item = BidLineItem(
                price_item=support_item,
                quantity=supports_needed,
                material_cost=material_cost,
                labor_cost=labor_cost,
                reason="Cable supports every 3 ft"
            )
            section.line_items.append(line_item)

        return section

    def _build_grounding_section(self, requirements: Dict[str, Any]) -> BidSection:
        """Build the Grounding System section."""
        section = BidSection(name="Grounding System")

        num_rods = requirements["total_rods"]

        # Find ground rod item
        item = self.find_item("ground rod")
        if not item:
            item = self.find_item("grounding")

        if item:
            material_cost = num_rods * item.unit_price
            labor_cost = (num_rods * item.labor_rate) if item.labor_rate else (num_rods * 50)  # $50 default per rod (drilling required)

            line_item = BidLineItem(
                price_item=item,
                quantity=num_rods,
                material_cost=material_cost,
                labor_cost=labor_cost,
                reason=requirements.get("notes", "Ground electrodes")
            )
            section.line_items.append(line_item)

        return section

    def _build_bonding_section(self, requirements: Dict[str, Any], material: str) -> BidSection:
        """Build the Bonding section (NFPA 780)."""
        section = BidSection(name="Bonding Connections")

        num_connections = requirements["total_connections"]
        wire_length = requirements.get("bonding_wire_ft", num_connections * 10)

        # Bonding wire
        item = self.find_item("bonding", prefer_material=material)
        if not item:
            item = self.find_item("wire", prefer_material=material)

        if item:
            material_cost = wire_length * item.unit_price
            labor_cost = (wire_length * item.labor_rate) if item.labor_rate else (num_connections * 25)  # $25 per connection

            line_item = BidLineItem(
                price_item=item,
                quantity=wire_length,
                material_cost=material_cost,
                labor_cost=labor_cost,
                reason=requirements.get("notes", "Bonding connections")
            )
            section.line_items.append(line_item)

        return section
