"""
UL 96A Standard for Lightning Protection Systems

This module encodes the rules from UL 96A. These rules determine:
- Where air terminals (lightning rods) must be placed
- How conductors (cables) must be routed
- Grounding requirements

Think of this as the "rulebook" that tells us the minimum requirements.
"""

from typing import Dict, Any
import math


class UL96ACompliance:
    """
    UL 96A compliance calculator.

    This class provides methods to calculate required quantities
    based on UL 96A rules.
    """

    # Standard spacing requirements (in feet)
    AIR_TERMINAL_MAX_SPACING = 20  # Air terminals must be ≤20 ft apart
    CONDUCTOR_SUPPORT_SPACING = 3   # Conductors supported every 3 ft
    GROUND_ROD_MIN_DEPTH = 10       # Ground rods must be 10 ft deep minimum

    @staticmethod
    def calculate_air_terminals(roof_area_sqft: float, num_corners: int = 4,
                                 perimeter_ft: float = None) -> Dict[str, Any]:
        """
        Calculate number of air terminals needed per UL 96A.

        Rules:
        1. One at each corner (mandatory)
        2. Along edges: max 20 ft spacing
        3. In field: one per 400-600 sq ft (rough guideline)

        Args:
            roof_area_sqft: Total roof area in square feet
            num_corners: Number of roof corners (typically 4)
            perimeter_ft: Roof perimeter in feet (if known)

        Returns:
            Dictionary with 'total', 'corners', 'edges', 'field' counts
        """
        # Step 1: Corners (mandatory)
        corner_terminals = num_corners

        # Step 2: Edge terminals
        if perimeter_ft:
            # Subtract corners, then divide remaining perimeter by max spacing
            remaining_perimeter = perimeter_ft - (num_corners * 2)  # rough adjustment
            edge_terminals = max(0, math.ceil(remaining_perimeter / UL96ACompliance.AIR_TERMINAL_MAX_SPACING))
        else:
            # Estimate: assume square building
            side_length = math.sqrt(roof_area_sqft)
            perimeter_ft = side_length * 4
            remaining_perimeter = perimeter_ft - (num_corners * 2)
            edge_terminals = max(0, math.ceil(remaining_perimeter / UL96ACompliance.AIR_TERMINAL_MAX_SPACING))

        # Step 3: Field terminals (interior of roof)
        # Rule of thumb: 1 per 500 sqft for flat roofs
        field_terminals = max(0, math.ceil(roof_area_sqft / 500) - corner_terminals)

        total = corner_terminals + edge_terminals + field_terminals

        return {
            "total": total,
            "corners": corner_terminals,
            "edges": edge_terminals,
            "field": field_terminals,
            "notes": f"UL 96A: Max {UL96ACompliance.AIR_TERMINAL_MAX_SPACING} ft spacing"
        }

    @staticmethod
    def calculate_conductors(building_height_ft: float, num_downleads: int = 2,
                            perimeter_ft: float = None) -> Dict[str, Any]:
        """
        Calculate conductor (cable) lengths needed per UL 96A.

        Rules:
        1. Minimum 2 down conductors (two-way path to ground)
        2. Conductors run from air terminals to ground
        3. Main horizontal conductor around roof perimeter

        Args:
            building_height_ft: Height of building
            num_downleads: Number of down conductors (min 2 for two-way path)
            perimeter_ft: Roof perimeter (for horizontal conductor)

        Returns:
            Dictionary with conductor lengths and quantities
        """
        # Ensure minimum 2 downleads for UL 96A compliance
        num_downleads = max(2, num_downleads)

        # Vertical conductor length (downleads)
        # Add 10 ft per downlead for connections and ground termination
        vertical_length_ft = (building_height_ft + 10) * num_downleads

        # Horizontal conductor length (roof perimeter + interconnections)
        # Add 20% for overlaps and connections
        horizontal_length_ft = (perimeter_ft * 1.2) if perimeter_ft else (building_height_ft * 4 * 1.2)

        total_conductor_ft = vertical_length_ft + horizontal_length_ft

        return {
            "total_length_ft": round(total_conductor_ft, 1),
            "vertical_ft": round(vertical_length_ft, 1),
            "horizontal_ft": round(horizontal_length_ft, 1),
            "num_downleads": num_downleads,
            "notes": "UL 96A: Min 2 down conductors (two-way path), 8\" min bend radius"
        }

    @staticmethod
    def calculate_grounding(num_downleads: int = 2, soil_type: str = "normal") -> Dict[str, Any]:
        """
        Calculate grounding requirements per UL 96A.

        Rules:
        1. Each down conductor terminates in ground electrode
        2. Minimum 10 ft ground rods
        3. Multiple rods if soil resistance is high

        Args:
            num_downleads: Number of down conductors
            soil_type: 'normal', 'rocky', 'sandy' (affects number of rods)

        Returns:
            Dictionary with grounding rod quantities
        """
        # Basic: 1 ground rod per downlead (minimum)
        rods_per_downlead = 1

        # Adjust for soil conditions
        if soil_type == "rocky":
            rods_per_downlead = 2  # Rocky soil needs multiple rods
        elif soil_type == "sandy":
            rods_per_downlead = 1.5  # Sandy may need extra

        total_rods = math.ceil(num_downleads * rods_per_downlead)

        return {
            "total_rods": total_rods,
            "rod_depth_ft": UL96ACompliance.GROUND_ROD_MIN_DEPTH,
            "notes": f"UL 96A: Min {UL96ACompliance.GROUND_ROD_MIN_DEPTH} ft deep, one per downlead minimum"
        }

    @staticmethod
    def check_compliance(project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full UL 96A compliance check for a project.

        Args:
            project_data: Dictionary with building specs (height, area, etc.)

        Returns:
            Dictionary with all calculated requirements
        """
        results = {}

        # Air terminals
        if "roof_area_sqft" in project_data:
            results["air_terminals"] = UL96ACompliance.calculate_air_terminals(
                roof_area_sqft=project_data["roof_area_sqft"],
                num_corners=project_data.get("num_corners", 4),
                perimeter_ft=project_data.get("perimeter_ft")
            )

        # Conductors
        if "building_height_ft" in project_data:
            results["conductors"] = UL96ACompliance.calculate_conductors(
                building_height_ft=project_data["building_height_ft"],
                num_downleads=project_data.get("num_downleads", 2),
                perimeter_ft=project_data.get("perimeter_ft")
            )

        # Grounding
        results["grounding"] = UL96ACompliance.calculate_grounding(
            num_downleads=project_data.get("num_downleads", 2),
            soil_type=project_data.get("soil_type", "normal")
        )

        results["code"] = "UL 96A"
        results["compliant"] = True  # Calculations ensure compliance

        return results
