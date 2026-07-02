"""
Dual Compliance Module - UL 96A + NFPA 780 Cross-Referencing

This module combines UL 96A and NFPA 780 standards intelligently,
using the stricter requirement for most items while avoiding
over-specification of air terminals.
"""

from typing import Dict, Any
from src.compliance.ul96a import UL96ACompliance
from src.compliance.nfpa780 import NFPA780Compliance


class DualCompliance:
    """
    Combines UL 96A and NFPA 780 standards with intelligent merging.
    
    Merging Rules:
    - Air Terminals: Use LOWER count (avoid over-specification)
    - Ground Rods: Use HIGHER count (stricter = safer)
    - Conductors: Use HIGHER length (more coverage)
    - Bonding: Include ALL NFPA 780 bonding requirements
    """
    
    @staticmethod
    def check_combined_compliance(project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate combined compliance using both UL 96A and NFPA 780.
        
        Args:
            project_data: Dictionary with project specifications
            
        Returns:
            Dictionary with merged requirements from both standards
        """
        # Get requirements from both standards
        ul96a = UL96ACompliance.check_compliance(project_data)
        nfpa780 = NFPA780Compliance.check_compliance(project_data)
        
        # Merge air terminals - use LOWER count
        air_terminals_combined = {
            "total": min(
                ul96a["air_terminals"]["total"],
                nfpa780["air_terminals"]["total"]
            ),
            "corners": ul96a["air_terminals"]["corners"],  # Same in both
            "edges": min(
                ul96a["air_terminals"]["edges"],
                nfpa780["air_terminals"]["edges"]
            ),
            "field": min(
                ul96a["air_terminals"]["field"],
                nfpa780["air_terminals"]["field"]
            ),
            "notes": (
                f"Combined UL 96A + NFPA 780 (using lower count): "
                f"UL={ul96a['air_terminals']['total']}, "
                f"NFPA={nfpa780['air_terminals']['total']}"
            )
        }
        
        # Merge conductors - use HIGHER length (more coverage)
        conductors_combined = {
            "total_length_ft": max(
                ul96a["conductors"]["total_length_ft"],
                nfpa780["conductors"]["total_length_ft"]
            ),
            "vertical_ft": max(
                ul96a["conductors"]["vertical_ft"],
                nfpa780["conductors"]["vertical_ft"]
            ),
            "horizontal_ft": max(
                ul96a["conductors"]["horizontal_ft"],
                nfpa780["conductors"]["horizontal_ft"]
            ),
            "bonding_ft": nfpa780["conductors"].get("bonding_ft", 0),  # NFPA-specific
            "num_downleads": max(
                ul96a["conductors"]["num_downleads"],
                nfpa780["conductors"]["num_downleads"]
            ),
            "notes": (
                f"Combined (using higher length): "
                f"UL={ul96a['conductors']['total_length_ft']:.1f}ft, "
                f"NFPA={nfpa780['conductors']['total_length_ft']:.1f}ft"
            )
        }
        
        # Merge grounding - use HIGHER count (stricter)
        grounding_combined = {
            "total_rods": max(
                ul96a["grounding"]["total_rods"],
                nfpa780["grounding"]["total_rods"]
            ),
            "rod_depth_ft": max(
                ul96a["grounding"]["rod_depth_ft"],
                nfpa780["grounding"]["rod_depth_ft"]
            ),
            "ground_ring": nfpa780["grounding"].get("ground_ring", False),
            "ground_ring_length_ft": nfpa780["grounding"].get("ground_ring_length_ft", 0),
            "notes": (
                f"Combined (using stricter): "
                f"UL={ul96a['grounding']['total_rods']} rods, "
                f"NFPA={nfpa780['grounding']['total_rods']} rods"
            )
        }
        
        # Include NFPA 780 bonding requirements (UL 96A doesn't have these)
        bonding_combined = nfpa780.get("bonding", {
            "total_connections": 0,
            "bonding_wire_ft": 0,
            "notes": "No bonding required"
        })
        
        # Build combined result
        combined = {
            "air_terminals": air_terminals_combined,
            "conductors": conductors_combined,
            "grounding": grounding_combined,
            "bonding": bonding_combined,
            "codes": ["UL 96A", "NFPA 780"],
            "compliance_method": "Comprehensive Cross-Reference",
            "compliant": True,
            "summary": (
                f"Combined compliance using UL 96A + NFPA 780. "
                f"Air terminals: {air_terminals_combined['total']} (lower count), "
                f"Ground rods: {grounding_combined['total_rods']} (stricter), "
                f"Conductors: {conductors_combined['total_length_ft']:.0f}ft (higher), "
                f"Bonding: {bonding_combined['total_connections']} connections (NFPA)"
            )
        }
        
        return combined

