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
import math
from src.models.items import PriceItem
from src.models.bid import Bid, BidSection, BidLineItem
from src.compliance.ul96a import UL96ACompliance
from src.compliance.nfpa780 import NFPA780Compliance
from src.compliance.dual_compliance import DualCompliance


class BidCalculator:
    """
    Main bid calculation engine.

    This class maps compliance requirements to pricing items and
    generates a complete bid.
    """

    def __init__(self, price_catalog: List[PriceItem], compliance_code: str = "DUAL"):
        """
        Initialize calculator with pricing catalog.

        Args:
            price_catalog: List of PriceItem objects from Excel
            compliance_code: Which code to use ('UL 96A', 'NFPA 780', or 'DUAL' for both)
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

    def find_item(self, search_term: str, prefer_material: Optional[str] = None, max_price: Optional[float] = None) -> Optional[PriceItem]:
        """
        Find a price item by search term, preferring standard items.

        Args:
            search_term: What to search for (e.g., "air terminal")
            prefer_material: Preferred material type (e.g., "copper", "aluminum")
            max_price: Maximum acceptable price (filters out specialty items)

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

        # Filter out specialty/expensive items by keywords
        specialty_keywords = ["dynasphere", "mk iv", "mkiv", "adaptor", "adapter", "kit"]
        filtered_candidates = []
        for item in candidates:
            item_name_lower = item.name.lower()
            is_specialty = any(keyword in item_name_lower for keyword in specialty_keywords)
            if not is_specialty:
                filtered_candidates.append(item)
        
        # Use filtered list if we have any standard items
        if filtered_candidates:
            candidates = filtered_candidates

        # If material preference specified, filter by material
        # Check both material_type field AND item name (ERICO has material in description)
        if prefer_material:
            material_filtered = []
            for item in candidates:
                # Check material_type field
                if item.material_type and prefer_material.lower() in item.material_type.lower():
                    material_filtered.append(item)
                # Also check item name/description
                elif prefer_material.lower() in item.name.lower():
                    material_filtered.append(item)
            
            if material_filtered:
                candidates = material_filtered

        # If max_price specified, filter by price
        if max_price:
            price_filtered = [item for item in candidates if item.unit_price <= max_price]
            if price_filtered:
                candidates = price_filtered

        # Sort by price and pick a mid-range option (avoid both cheapest and most expensive)
        if len(candidates) > 2:
            candidates.sort(key=lambda x: x.unit_price)
            # Return item at 30th percentile (slightly below middle)
            index = int(len(candidates) * 0.3)
            return candidates[index]
        elif candidates:
            return candidates[0]
        
        return None

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
                - labor_markup_pct: float (optional, default 20.0)
                - overhead_pct: float (optional, default 10.0)
                - profit_pct: float (optional, default 10.0)
                - commission_amount: float (optional, default 0.0)
                - tools_rental_amount: float (optional, default 0.0)

        Returns:
            Complete Bid object with all sections and line items
        """
        # Step 1: Get compliance requirements
        if self.compliance_code == "DUAL":
            # Use combined compliance (default)
            compliance = DualCompliance.check_combined_compliance(project_data)
        elif self.compliance_code == "UL 96A":
            compliance = UL96ACompliance.check_compliance(project_data)
        else:  # NFPA 780
            compliance = NFPA780Compliance.check_compliance(project_data)

        compliance = self._apply_component_overrides(compliance, project_data)

        # Step 2: Create bid object with pricing settings
        bid = Bid(
            project_name=project_data.get("project_name", "Lightning Protection Bid"),
            labor_markup_pct=project_data.get("labor_markup_pct", 20.0),
            overhead_pct=project_data.get("overhead_pct", 10.0),
            profit_pct=project_data.get("profit_pct", 10.0),
            commission_amount=project_data.get("commission_amount", 0.0),
            tools_rental_amount=project_data.get("tools_rental_amount", 0.0),
            tools_rental_type=project_data.get("tools_rental_type", "$"),
            shipping_amount=project_data.get("shipping_amount", 0.0),
            use_tax_pct=project_data.get("use_tax_pct", 0.0),
            minimum_bid_amount=project_data.get("minimum_bid_amount", 0.0),
            rounding_increment=project_data.get("rounding_increment", 0.0),
            rounding_mode=project_data.get("rounding_mode", "none"),
            custom_pricing_adjustments=project_data.get("custom_pricing_adjustments", []),
        )

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

    def _apply_component_overrides(self, compliance: Dict[str, Any], project_data: Dict[str, Any]) -> Dict[str, Any]:
        overrides = dict(project_data.get("component_overrides") or {})
        if not overrides:
            return compliance

        building_height_ft = float(project_data.get("building_height_ft") or 0.0)
        perimeter_ft = float(project_data.get("perimeter_ft") or 0.0)

        air_terminals_total = overrides.get("air_terminals")
        if air_terminals_total is not None and "air_terminals" in compliance:
            original_total = compliance["air_terminals"].get("total", 0)
            compliance["air_terminals"]["total"] = max(0, int(round(float(air_terminals_total))))
            compliance["air_terminals"]["notes"] = (
                f"{compliance['air_terminals'].get('notes', '')} | Manual work plan override "
                f"(was {original_total}, now {compliance['air_terminals']['total']})"
            ).strip()

        downleads_total = overrides.get("downleads")
        if downleads_total is not None and "conductors" in compliance:
            num_downleads = max(2, int(round(float(downleads_total))))
            vertical_ft = (building_height_ft + 10.0) * num_downleads if building_height_ft > 0 else 0.0
            horizontal_ft = float(compliance["conductors"].get("horizontal_ft") or 0.0)
            if horizontal_ft <= 0 and perimeter_ft > 0:
                horizontal_ft = perimeter_ft * 1.2
            compliance["conductors"]["num_downleads"] = num_downleads
            compliance["conductors"]["vertical_ft"] = round(vertical_ft, 1)
            compliance["conductors"]["horizontal_ft"] = round(horizontal_ft, 1)
            compliance["conductors"]["total_length_ft"] = round(vertical_ft + horizontal_ft, 1)
            compliance["conductors"]["notes"] = (
                f"{compliance['conductors'].get('notes', '')} | Manual work plan override "
                f"(downleads={num_downleads})"
            ).strip()

        ground_rods_total = overrides.get("ground_rods")
        if ground_rods_total is not None and "grounding" in compliance:
            original_rods = compliance["grounding"].get("total_rods", 0)
            compliance["grounding"]["total_rods"] = max(0, int(round(float(ground_rods_total))))
            compliance["grounding"]["notes"] = (
                f"{compliance['grounding'].get('notes', '')} | Manual work plan override "
                f"(was {original_rods}, now {compliance['grounding']['total_rods']})"
            ).strip()

        bonding_connections_total = overrides.get("bonding_connections")
        if bonding_connections_total is not None:
            total_connections = max(0, int(round(float(bonding_connections_total))))
            bonding_wire_ft = float(compliance.get("bonding", {}).get("bonding_wire_ft") or 0.0)
            if not bonding_wire_ft:
                bonding_wire_ft = total_connections * 10.0
            compliance.setdefault("bonding", {})
            compliance["bonding"]["total_connections"] = total_connections
            compliance["bonding"]["bonding_wire_ft"] = round(bonding_wire_ft, 1)
            compliance["bonding"]["notes"] = (
                f"{compliance['bonding'].get('notes', '')} | Manual work plan override "
                f"(connections={total_connections})"
            ).strip()

        return compliance

    def _build_air_terminal_section(self, requirements: Dict[str, Any], material: str) -> BidSection:
        """Build the Air Terminals section of the bid."""
        section = BidSection(name="Air Terminals")

        quantity = requirements["total"]

        # Find air terminal item from catalog (max $100 to avoid specialty items)
        item = self.find_item("air terminal", prefer_material=material, max_price=100)
        if not item:
            item = self.find_item("terminal", max_price=100)  # fallback

        if item:
            material_cost = quantity * item.unit_price
            labor_cost = 0  # Labor set by worker configuration, not catalog

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
            labor_cost = 0  # Labor set by worker configuration, not catalog

            line_item = BidLineItem(
                price_item=item,
                quantity=total_length,
                material_cost=material_cost,
                labor_cost=labor_cost,
                reason=requirements.get("notes", "Lightning conductor cables")
            )
            section.line_items.append(line_item)

        # Add fasteners/supports (every 3 ft)
        supports_needed = math.ceil(total_length / 3)
        support_item = self.find_item("clamp")
        if not support_item:
            support_item = self.find_item("connector")

        if support_item:
            material_cost = supports_needed * support_item.unit_price
            labor_cost = 0  # Labor set by worker configuration, not catalog

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
            labor_cost = 0  # Labor set by worker configuration, not catalog

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
            labor_cost = 0  # Labor set by worker configuration, not catalog

            line_item = BidLineItem(
                price_item=item,
                quantity=wire_length,
                material_cost=material_cost,
                labor_cost=labor_cost,
                reason=requirements.get("notes", "Bonding connections")
            )
            section.line_items.append(line_item)

        return section
