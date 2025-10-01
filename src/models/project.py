"""
Project data models for LightningBid system.

These classes represent the project information extracted from PDFs
and user inputs. Think of these as the "blueprint" of what needs to be protected.
"""

from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import date


class BuildingInfo(BaseModel):
    """Information about the building to be protected."""
    name: str
    height_ft: Optional[float] = None
    roof_area_sqft: Optional[float] = None
    roof_type: Optional[str] = None  # flat, pitched, etc.
    num_corners: Optional[int] = None
    has_metal_roof: bool = False


class SpecRequirement(BaseModel):
    """A specific requirement from the PDF specification."""
    category: str  # 'air_terminal', 'conductor', 'grounding', 'bonding'
    description: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    compliance_codes: List[str] = []  # ['UL 96A', 'NFPA 780']
    page_reference: Optional[str] = None


class Project(BaseModel):
    """
    Main project container - represents one lightning protection bid.

    This holds everything we know about the project: building details,
    requirements from specs, and which compliance codes apply.
    """
    name: str
    location: Optional[str] = None
    bid_date: date = date.today()

    # Building information
    building: Optional[BuildingInfo] = None

    # Requirements extracted from PDFs
    requirements: List[SpecRequirement] = []

    # Compliance codes that apply
    compliance_codes: List[str] = []  # ['UL 96A', 'NFPA 780']

    # Raw data from PDF parsing (for debugging/reference)
    spec_terms: Dict[str, List[str]] = {}
