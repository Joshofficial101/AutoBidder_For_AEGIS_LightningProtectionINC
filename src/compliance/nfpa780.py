"""
NFPA 780 Standard for Lightning Protection Systems

This module encodes rules from NFPA 780. NFPA 780 is similar to UL 96A
but has some different spacing requirements and additional bonding rules.

Key differences from UL 96A:
- Allows 25 ft spacing for air terminals (vs 20 ft in UL 96A)
- More detailed bonding requirements for metal objects
- Specific rules for different structure types
"""

from typing import Dict, Any
import math


class NFPA780Compliance:
    """
    NFPA 780 compliance calculator.

    Similar to UL 96A but with some different spacing and requirements.
    """

    # NFPA 780 spacing (slightly more lenient than UL 96A)
    AIR_TERMINAL_MAX_SPACING = 25  # 25 ft for NFPA 780 (vs 20 ft UL 96A)
    CONDUCTOR_SUPPORT_SPACING = 3
    GROUND_ROD_MIN_DEPTH = 10
    BONDING_WIRE_SIZE_AWG = 6  # #6 AWG minimum for bonding

    @staticmethod
    def calculate_air_terminals(roof_area_sqft: float, num_corners: int = 4,
                                 perimeter_ft: float = None,
                                 structure_type: str = "normal") -> Dict[str, Any]:
        """
        Calculate air terminals per NFPA 780.

        Similar to UL 96A but allows 25 ft spacing.

        Args:
            roof_area_sqft: Roof area in square feet
            num_corners: Number of corners
            perimeter_ft: Perimeter length
            structure_type: 'normal', 'tall', 'complex'

        Returns:
            Dictionary with terminal counts
        """
        corner_terminals = num_corners

        # NFPA 780 allows slightly wider spacing
        max_spacing = NFPA780Compliance.AIR_TERMINAL_MAX_SPACING

        # Adjust for structure type
        if structure_type == "tall":
            max_spacing = 20  # Taller structures need tighter spacing
        elif structure_type == "complex":
            max_spacing = 15  # Complex roofs need more coverage

        if perimeter_ft:
            remaining_perimeter = perimeter_ft - (num_corners * 2)
            edge_terminals = max(0, math.ceil(remaining_perimeter / max_spacing))
        else:
            side_length = math.sqrt(roof_area_sqft)
            perimeter_ft = side_length * 4
            remaining_perimeter = perimeter_ft - (num_corners * 2)
            edge_terminals = max(0, math.ceil(remaining_perimeter / max_spacing))

        # Field terminals
        field_terminals = max(0, math.ceil(roof_area_sqft / 600) - corner_terminals)

        total = corner_terminals + edge_terminals + field_terminals

        return {
            "total": total,
            "corners": corner_terminals,
            "edges": edge_terminals,
            "field": field_terminals,
            "notes": f"NFPA 780: Max {max_spacing} ft spacing, {structure_type} structure"
        }

    @staticmethod
    def calculate_conductors(building_height_ft: float, num_downleads: int = 2,
                            perimeter_ft: float = None,
                            has_metal_roof: bool = False) -> Dict[str, Any]:
        """
        Calculate conductors per NFPA 780.

        Args:
            building_height_ft: Building height
            num_downleads: Number of down conductors
            perimeter_ft: Roof perimeter
            has_metal_roof: Whether roof is metal (affects bonding)

        Returns:
            Dictionary with conductor requirements
        """
        num_downleads = max(2, num_downleads)

        vertical_length_ft = (building_height_ft + 10) * num_downleads
        horizontal_length_ft = (perimeter_ft * 1.2) if perimeter_ft else (building_height_ft * 4 * 1.2)

        # NFPA 780: If metal roof, need additional bonding conductor
        bonding_length_ft = 0
        if has_metal_roof:
            bonding_length_ft = perimeter_ft * 0.5 if perimeter_ft else (building_height_ft * 2)

        total_conductor_ft = vertical_length_ft + horizontal_length_ft + bonding_length_ft

        return {
            "total_length_ft": round(total_conductor_ft, 1),
            "vertical_ft": round(vertical_length_ft, 1),
            "horizontal_ft": round(horizontal_length_ft, 1),
            "bonding_ft": round(bonding_length_ft, 1) if has_metal_roof else 0,
            "num_downleads": num_downleads,
            "notes": "NFPA 780: Min 2 paths, metal roof bonding required" if has_metal_roof else "NFPA 780: Min 2 down paths"
        }

    @staticmethod
    def calculate_bonding(metal_objects: int = 0, has_metal_roof: bool = False) -> Dict[str, Any]:
        """
        Calculate bonding requirements per NFPA 780.

        NFPA 780 requires bonding all metal objects within 6 ft of
        lightning protection system.

        Args:
            metal_objects: Number of metal objects to bond (HVAC, pipes, etc.)
            has_metal_roof: Whether building has metal roof

        Returns:
            Dictionary with bonding requirements
        """
        # Bonding connections needed
        bonding_connections = metal_objects

        if has_metal_roof:
            bonding_connections += 4  # Metal roof needs bonding at corners

        # Bonding wire footage (estimate 10 ft per connection)
        bonding_wire_ft = bonding_connections * 10

        return {
            "total_connections": bonding_connections,
            "bonding_wire_ft": bonding_wire_ft,
            "wire_size_awg": NFPA780Compliance.BONDING_WIRE_SIZE_AWG,
            "notes": "NFPA 780: Bond all metal within 6 ft of system"
        }

    @staticmethod
    def calculate_grounding(num_downleads: int = 2, soil_type: str = "normal",
                           ground_ring: bool = False) -> Dict[str, Any]:
        """
        Calculate grounding per NFPA 780.

        NFPA 780 encourages ground rings for larger structures.

        Args:
            num_downleads: Number of down conductors
            soil_type: Soil condition
            ground_ring: Whether to include ground ring

        Returns:
            Dictionary with grounding requirements
        """
        rods_per_downlead = 1

        if soil_type == "rocky":
            rods_per_downlead = 2
        elif soil_type == "sandy":
            rods_per_downlead = 1.5

        total_rods = math.ceil(num_downleads * rods_per_downlead)

        result = {
            "total_rods": total_rods,
            "rod_depth_ft": NFPA780Compliance.GROUND_ROD_MIN_DEPTH,
            "ground_ring": ground_ring,
            "notes": f"NFPA 780: {total_rods} rods at {NFPA780Compliance.GROUND_ROD_MIN_DEPTH} ft depth"
        }

        if ground_ring:
            # Ground ring perimeter (rough estimate)
            result["ground_ring_length_ft"] = num_downleads * 25  # 25 ft between rods
            result["notes"] += ", ground ring recommended"

        return result

    @staticmethod
    def check_compliance(project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full NFPA 780 compliance check.

        Args:
            project_data: Project specifications

        Returns:
            Dictionary with all requirements
        """
        results = {}

        # Air terminals
        if "roof_area_sqft" in project_data:
            results["air_terminals"] = NFPA780Compliance.calculate_air_terminals(
                roof_area_sqft=project_data["roof_area_sqft"],
                num_corners=project_data.get("num_corners", 4),
                perimeter_ft=project_data.get("perimeter_ft"),
                structure_type=project_data.get("structure_type", "normal")
            )

        # Conductors
        if "building_height_ft" in project_data:
            results["conductors"] = NFPA780Compliance.calculate_conductors(
                building_height_ft=project_data["building_height_ft"],
                num_downleads=project_data.get("num_downleads", 2),
                perimeter_ft=project_data.get("perimeter_ft"),
                has_metal_roof=project_data.get("has_metal_roof", False)
            )

        # Bonding
        results["bonding"] = NFPA780Compliance.calculate_bonding(
            metal_objects=project_data.get("metal_objects", 0),
            has_metal_roof=project_data.get("has_metal_roof", False)
        )

        # Grounding
        results["grounding"] = NFPA780Compliance.calculate_grounding(
            num_downleads=project_data.get("num_downleads", 2),
            soil_type=project_data.get("soil_type", "normal"),
            ground_ring=project_data.get("ground_ring", False)
        )

        results["code"] = "NFPA 780"
        results["compliant"] = True

        return results
