export type HealthResponse = {
  status: string;
};

export type HealthCheckResult = {
  status: "ok" | "degraded" | "fail";
  required: boolean;
  message: string;
  duration_ms: number;
  metadata?: Record<string, unknown>;
};

export type HealthReadinessResponse = {
  status: "ok" | "degraded" | "fail";
  ready: boolean;
  timestamp: string;
  checks: Record<string, HealthCheckResult>;
};

export type AuthUser = {
  user_id: number;
  username: string;
  backup_code?: string;
};

export type LoginRequest = {
  username: string;
  password: string;
};

export type RegisterRequest = {
  username: string;
  email: string;
  password: string;
};

export type ResetPasswordBackupRequest = {
  username: string;
  backup_code: string;
  new_password: string;
};

export type BidPreviewRequest = {
  pricing_file_path: string;
  pricing_sheet?: string;
  compliance_code?: string;
  project_data: Record<string, unknown>;
  workers?: Array<{ name: string; wage_per_hour: number; hours: number }>;
};

export type BidPreviewUploadRequest = {
  pricing_sheet?: string;
  compliance_code?: string;
  project_data: Record<string, unknown>;
  workers?: Array<{ name: string; wage_per_hour: number; hours: number }>;
};

export type BidPreviewBase64Request = BidPreviewUploadRequest & {
  file_name?: string;
  pricing_file_base64: string;
};

export type SectionSummary = {
  name: string;
  items: number;
  material_total: number;
  labor_total: number;
  section_total: number;
};

export type CalculationLineItem = {
  key: string;
  label: string;
  amount: number;
};

export type CustomPricingAdjustmentApplied = {
  name: string;
  mode: string;
  value: number;
  applied_amount: number;
};

export type CalculationBreakdown = {
  currency: string;
  line_items: CalculationLineItem[];
  custom_adjustments: CustomPricingAdjustmentApplied[];
  inputs: {
    material_markup_pct: number;
    labor_markup_pct: number;
    overhead_pct: number;
    profit_pct: number;
    commission_amount: number;
    tools_rental_amount: number;
    tools_rental_type: string;
    shipping_amount: number;
    use_tax_pct: number;
    minimum_bid_amount: number;
    rounding_mode: string;
    rounding_increment: number;
  };
  totals: {
    subtotal: number;
    total_with_markup: number;
    base_final_before_custom: number;
    custom_adjustments_total: number;
    final_before_floor_rounding: number;
    minimum_floor_adjustment: number;
    rounding_adjustment: number;
    final_bid_amount: number;
  };
};

export type BidPreviewResponse = {
  project_name: string;
  subtotal: number;
  total_with_markup: number;
  final_bid_amount: number;
  material_total: number;
  labor_total: number;
  calculation_breakdown: CalculationBreakdown;
  sections: SectionSummary[];
};

export type ParsePdfRequest = {
  pdf_file_path: string;
};

export type ParsePdfBase64Request = {
  file_name?: string;
  file_bytes_base64: string;
};

export type ParsePdfResponse = {
  extracted: {
    building_dimensions?: {
      height?: number | null;
      area?: number | null;
      perimeter?: number | null;
      width?: number | null;
      length?: number | null;
    };
    project_info?: {
      project_name?: string | null;
    };
    num_corners?: number | null;
    [key: string]: unknown;
  };
};

export type DashboardJobItem = {
  job_id: number;
  project_name: string;
  status: string;
  status_display: string;
  bid_amount: number;
  scheduled_date?: string | null;
  start_date?: string | null;
  completion_date?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  assigned_crew?: string[];
};

export type DashboardSummaryResponse = {
  user_id: number;
  metrics: {
    active_jobs: number;
    completed_jobs: number;
    total_revenue: number;
    total_profit: number;
    profit_margin_pct: number;
  };
  overdue_jobs: DashboardJobItem[];
  todays_jobs: DashboardJobItem[];
  upcoming_jobs: DashboardJobItem[];
  recent_jobs: DashboardJobItem[];
};

export type JobBoardStatus =
  | "awaiting_approval"
  | "scheduled"
  | "in_progress"
  | "inspection"
  | "completed"
  | "invoiced";

export type JobsBoardResponse = {
  user_id: number;
  awaiting_approval: DashboardJobItem[];
  scheduled: DashboardJobItem[];
  in_progress: DashboardJobItem[];
  inspection: DashboardJobItem[];
  completed: DashboardJobItem[];
  invoiced: DashboardJobItem[];
};

export type JobStatusUpdateRequest = {
  user_id?: number;
  new_status: JobBoardStatus;
  start_date?: string;
  completion_date?: string;
  invoice_date?: string;
  invoice_number?: string;
  assigned_crew?: string[];
  note?: string;
};

export type JobStatusUpdateResponse = {
  user_id: number;
  job: DashboardJobItem;
};

export type JobApproveRequest = {
  user_id?: number;
  scheduled_date: string;
  assigned_crew?: string[];
  note?: string;
};

export type JobApproveResponse = {
  user_id: number;
  job: DashboardJobItem;
};

export type CalendarJobItem = {
  job_id: number;
  project_name: string;
  status: string;
  status_display: string;
  bid_amount: number;
  scheduled_date?: string | null;
  start_date?: string | null;
  completion_date?: string | null;
  assigned_crew: string[];
};

export type CalendarJobsResponse = {
  user_id: number;
  start_date: string;
  end_date: string;
  jobs: CalendarJobItem[];
  available_crews: string[];
};

export type CalendarDayResponse = {
  user_id: number;
  date: string;
  jobs: CalendarJobItem[];
};
