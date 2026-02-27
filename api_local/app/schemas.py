from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, FilePath, field_validator

from app.settings import MAX_EXCEL_BASE64_CHARS, MAX_PDF_BASE64_CHARS


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ComplianceCode(str, Enum):
    DUAL = "DUAL"
    UL_96A = "UL 96A"
    NFPA_780 = "NFPA 780"


class JobBoardStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    INSPECTION = "inspection"
    COMPLETED = "completed"
    INVOICED = "invoiced"


class CalendarStatusFilter(str, Enum):
    ALL = "all"
    AWAITING_APPROVAL = "awaiting_approval"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    INSPECTION = "inspection"
    COMPLETED = "completed"
    INVOICED = "invoiced"


class HealthResponse(ApiModel):
    status: str = Field(examples=["ok"])


class HealthCheckResult(ApiModel):
    status: str = Field(examples=["ok", "degraded", "fail"])
    required: bool = True
    message: str
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthReadinessResponse(ApiModel):
    status: str = Field(examples=["ok", "degraded", "fail"])
    ready: bool
    timestamp: str
    checks: Dict[str, HealthCheckResult] = Field(default_factory=dict)


class RootResponse(ApiModel):
    service: str = Field(examples=["lightningbid-local-api"])
    status: str = Field(examples=["ok"])
    api_version: str = Field(examples=["v1"])
    docs_url: str = Field(examples=["/api/v1/docs"])
    openapi_url: str = Field(examples=["/api/v1/openapi.json"])


class WorkerIn(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    wage_per_hour: float = Field(default=0.0, ge=0)
    hours: float = Field(default=0.0, ge=0)


class BidPreviewRequest(ApiModel):
    pricing_file_path: FilePath
    pricing_sheet: Optional[str] = Field(default=None, min_length=1, max_length=120)
    compliance_code: ComplianceCode = ComplianceCode.DUAL
    project_data: Dict[str, Any]
    workers: List[WorkerIn] = Field(default_factory=list)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "pricing_file_path": "C:/Pricing/ERICO Installer 6.1.25 Price List.xlsx",
                "pricing_sheet": "Sheet1",
                "compliance_code": "DUAL",
                "project_data": {
                    "project_name": "AEGIS Distribution Center",
                    "building_height_ft": 35,
                    "roof_area_sqft": 5000,
                    "perimeter_ft": 284,
                },
                "workers": [
                    {
                        "name": "Lead Installer",
                        "wage_per_hour": 42.5,
                        "hours": 18,
                    }
                ],
            }
        },
    )

    @field_validator("pricing_file_path")
    @classmethod
    def validate_pricing_file_extension(cls, value: Path) -> Path:
        if value.suffix.lower() not in {".xlsx", ".xlsm", ".xls"}:
            raise ValueError("pricing_file_path must be an Excel file (.xlsx, .xlsm, .xls).")
        return value


class BidPreviewBase64Request(ApiModel):
    file_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    pricing_file_base64: str = Field(min_length=1, max_length=MAX_EXCEL_BASE64_CHARS)
    pricing_sheet: Optional[str] = Field(default=None, min_length=1, max_length=120)
    compliance_code: ComplianceCode = ComplianceCode.DUAL
    project_data: Dict[str, Any]
    workers: List[WorkerIn] = Field(default_factory=list)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "file_name": "ERICO Installer 6.1.25 Price List.xlsx",
                "pricing_file_base64": "<base64-encoded-xlsx>",
                "pricing_sheet": "Sheet1",
                "compliance_code": "DUAL",
                "project_data": {
                    "project_name": "AEGIS Distribution Center",
                    "building_height_ft": 35,
                    "roof_area_sqft": 5000,
                    "perimeter_ft": 284,
                },
                "workers": [],
            }
        },
    )

    @field_validator("file_name")
    @classmethod
    def validate_base64_pricing_file_name(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        suffix = Path(value).suffix.lower()
        if suffix and suffix not in {".xlsx", ".xlsm", ".xls"}:
            raise ValueError("file_name must use an Excel extension (.xlsx, .xlsm, .xls).")
        return value


class SectionSummary(ApiModel):
    name: str
    items: int
    material_total: float
    labor_total: float
    section_total: float


class CalculationLineItem(ApiModel):
    key: str
    label: str
    amount: float


class CustomPricingAdjustmentApplied(ApiModel):
    name: str
    mode: str
    value: float
    applied_amount: float


class CalculationBreakdownInputs(ApiModel):
    material_markup_pct: float
    labor_markup_pct: float
    overhead_pct: float
    profit_pct: float
    commission_amount: float
    tools_rental_amount: float
    tools_rental_type: str
    shipping_amount: float
    use_tax_pct: float
    minimum_bid_amount: float
    rounding_mode: str
    rounding_increment: float


class CalculationBreakdownTotals(ApiModel):
    subtotal: float
    total_with_markup: float
    base_final_before_custom: float
    custom_adjustments_total: float
    final_before_floor_rounding: float
    minimum_floor_adjustment: float
    rounding_adjustment: float
    final_bid_amount: float


class CalculationBreakdown(ApiModel):
    currency: str = "USD"
    line_items: List[CalculationLineItem] = Field(default_factory=list)
    custom_adjustments: List[CustomPricingAdjustmentApplied] = Field(default_factory=list)
    inputs: CalculationBreakdownInputs
    totals: CalculationBreakdownTotals


class BidPreviewResponse(ApiModel):
    project_name: str
    subtotal: float
    total_with_markup: float
    final_bid_amount: float
    material_total: float
    labor_total: float
    calculation_breakdown: CalculationBreakdown
    sections: List[SectionSummary]


class ParsePdfRequest(ApiModel):
    pdf_file_path: FilePath

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "pdf_file_path": "C:/Projects/BC23-001053 Electrical Building Plans.pdf",
            }
        },
    )

    @field_validator("pdf_file_path")
    @classmethod
    def validate_pdf_file_extension(cls, value: Path) -> Path:
        if value.suffix.lower() != ".pdf":
            raise ValueError("pdf_file_path must be a .pdf file.")
        return value


class ParsePdfResponse(ApiModel):
    extracted: Dict[str, Any]


class ParsePdfBase64Request(ApiModel):
    file_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    file_bytes_base64: str = Field(min_length=1, max_length=MAX_PDF_BASE64_CHARS)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "file_name": "electrical-plans.pdf",
                "file_bytes_base64": "<base64-encoded-pdf>",
            }
        },
    )

    @field_validator("file_name")
    @classmethod
    def validate_base64_pdf_file_name(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        suffix = Path(value).suffix.lower()
        if suffix and suffix != ".pdf":
            raise ValueError("file_name must use a .pdf extension.")
        return value


class ApiError(ApiModel):
    code: str = Field(examples=["VALIDATION_ERROR"])
    message: str = Field(examples=["Request validation failed."])
    detail: Optional[str] = Field(default=None, examples=["pricing_file_path is required"])
    errors: Optional[List[Dict[str, Any]]] = None


class DashboardJobItem(ApiModel):
    job_id: int
    project_name: str
    status: str
    status_display: str
    bid_amount: float = 0.0
    scheduled_date: Optional[str] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    assigned_crew: List[str] = Field(default_factory=list)


class DashboardMetrics(ApiModel):
    active_jobs: int
    completed_jobs: int
    total_revenue: float
    total_profit: float
    profit_margin_pct: float


class DashboardSummaryResponse(ApiModel):
    user_id: int
    metrics: DashboardMetrics
    overdue_jobs: List[DashboardJobItem] = Field(default_factory=list)
    todays_jobs: List[DashboardJobItem] = Field(default_factory=list)
    upcoming_jobs: List[DashboardJobItem] = Field(default_factory=list)
    recent_jobs: List[DashboardJobItem] = Field(default_factory=list)


class JobsBoardResponse(ApiModel):
    user_id: int
    awaiting_approval: List[DashboardJobItem] = Field(default_factory=list)
    scheduled: List[DashboardJobItem] = Field(default_factory=list)
    in_progress: List[DashboardJobItem] = Field(default_factory=list)
    inspection: List[DashboardJobItem] = Field(default_factory=list)
    completed: List[DashboardJobItem] = Field(default_factory=list)
    invoiced: List[DashboardJobItem] = Field(default_factory=list)


class JobStatusUpdateRequest(ApiModel):
    new_status: JobBoardStatus
    start_date: Optional[date] = None
    completion_date: Optional[date] = None
    invoice_date: Optional[date] = None
    invoice_number: Optional[str] = Field(default=None, min_length=1, max_length=80)
    assigned_crew: Optional[List[str]] = None
    note: Optional[str] = Field(default=None, max_length=500)


class JobStatusUpdateResponse(ApiModel):
    user_id: int
    job: DashboardJobItem


class JobApproveRequest(ApiModel):
    scheduled_date: date
    assigned_crew: List[str] = Field(default_factory=list)
    note: Optional[str] = Field(default=None, max_length=500)


class JobApproveResponse(ApiModel):
    user_id: int
    job: DashboardJobItem


class CalendarJobItem(ApiModel):
    job_id: int
    project_name: str
    status: str
    status_display: str
    bid_amount: float = 0.0
    scheduled_date: Optional[str] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    assigned_crew: List[str] = Field(default_factory=list)


class CalendarJobsResponse(ApiModel):
    user_id: int
    start_date: str
    end_date: str
    jobs: List[CalendarJobItem] = Field(default_factory=list)
    available_crews: List[str] = Field(default_factory=list)


class CalendarDayResponse(ApiModel):
    user_id: int
    date: str
    jobs: List[CalendarJobItem] = Field(default_factory=list)


class LoginRequest(ApiModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class RegisterRequest(ApiModel):
    username: str = Field(min_length=3, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class ResetPasswordBackupRequest(ApiModel):
    username: str = Field(min_length=1, max_length=120)
    backup_code: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=12, max_length=128)


class VerifyPasswordRequest(ApiModel):
    password: str = Field(min_length=1, max_length=256)


class VerifyPasswordResponse(ApiModel):
    valid: bool


class AuthUserResponse(ApiModel):
    user_id: int
    username: str
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    backup_code: Optional[str] = None


class AuthLogoutResponse(ApiModel):
    status: str = "ok"
