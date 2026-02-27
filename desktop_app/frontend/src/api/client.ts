import {
  AuthLogoutResponse,
  AuthUser,
  BidPreviewBase64Request,
  BidPreviewRequest,
  BidPreviewResponse,
  BidPreviewUploadRequest,
  CalendarDayResponse,
  CalendarJobsResponse,
  DashboardSummaryResponse,
  HealthReadinessResponse,
  HealthResponse,
  LoginRequest,
  JobApproveRequest,
  JobApproveResponse,
  JobStatusUpdateRequest,
  JobStatusUpdateResponse,
  JobsBoardResponse,
  ParsePdfBase64Request,
  ParsePdfRequest,
  ParsePdfResponse,
  ResetPasswordBackupRequest,
  RegisterRequest,
  VerifyPasswordRequest,
  VerifyPasswordResponse,
} from "./types";

const API_BASE = "http://127.0.0.1:8765";
let authToken: string | null = null;
let authFailureHandler: ((message: string) => void) | null = null;

export function setAuthToken(token: string | null): void {
  const normalized = (token ?? "").trim();
  authToken = normalized ? normalized : null;
}

export function setAuthFailureHandler(handler: ((message: string) => void) | null): void {
  authFailureHandler = handler;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (authToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!res.ok) {
    const body = await res.text();
    let message = body || `Request failed: ${res.status}`;
    if (body) {
      try {
        const parsed = JSON.parse(body) as { detail?: unknown; message?: unknown };
        if (typeof parsed.detail === "string" && parsed.detail.trim()) {
          message = parsed.detail;
        } else if (typeof parsed.message === "string" && parsed.message.trim()) {
          message = parsed.message;
        }
      } catch {
        // Keep raw body when it's not JSON.
      }
    }
    if (res.status === 401) {
      authToken = null;
      const authMessage = message || "Session expired. Please sign in again.";
      authFailureHandler?.(authMessage);
    }
    throw new Error(message);
  }

  return (await res.json()) as T;
}

async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const headers = new Headers(init?.headers ?? {});
  if (authToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!res.ok) {
    const body = await res.text();
    let message = body || `Request failed: ${res.status}`;
    if (body) {
      try {
        const parsed = JSON.parse(body) as { detail?: unknown; message?: unknown };
        if (typeof parsed.detail === "string" && parsed.detail.trim()) {
          message = parsed.detail;
        } else if (typeof parsed.message === "string" && parsed.message.trim()) {
          message = parsed.message;
        }
      } catch {
        // Keep raw body when it's not JSON.
      }
    }
    if (res.status === 401) {
      authToken = null;
      const authMessage = message || "Session expired. Please sign in again.";
      authFailureHandler?.(authMessage);
    }
    throw new Error(message);
  }

  return res.blob();
}

function isNotFoundError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  return error.message.includes("404") || error.message.includes("Not Found");
}

function getNativeFilePath(file: File): string | null {
  const candidate = (file as File & { path?: string }).path;
  if (typeof candidate === "string" && candidate.trim()) {
    return candidate.trim();
  }
  return null;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function getHealthReadiness(): Promise<HealthReadinessResponse> {
  const res = await fetch(`${API_BASE}/health/ready`);
  const body = await res.text();

  let parsed: unknown = null;
  if (body) {
    try {
      parsed = JSON.parse(body);
    } catch {
      parsed = null;
    }
  }

  if (parsed && typeof parsed === "object" && "ready" in parsed) {
    return parsed as HealthReadinessResponse;
  }

  if (!res.ok) {
    throw new Error(`Readiness check failed: ${res.status}`);
  }

  throw new Error("Readiness check returned an invalid response payload.");
}

export function login(payload: LoginRequest): Promise<AuthUser> {
  return request<AuthUser>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function register(payload: RegisterRequest): Promise<AuthUser> {
  return request<AuthUser>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resetPasswordWithBackupCode(payload: ResetPasswordBackupRequest): Promise<AuthUser> {
  return request<AuthUser>("/api/v1/auth/reset-password/backup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logoutSession(): Promise<AuthLogoutResponse> {
  return request<AuthLogoutResponse>("/api/v1/auth/logout", {
    method: "POST",
  });
}

export function verifyPassword(payload: VerifyPasswordRequest): Promise<VerifyPasswordResponse> {
  return request<VerifyPasswordResponse>("/api/v1/auth/verify-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function previewBid(payload: BidPreviewRequest): Promise<BidPreviewResponse> {
  return request<BidPreviewResponse>("/api/v1/bids/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function exportBidExcel(payload: BidPreviewRequest): Promise<Blob> {
  return requestBlob("/api/v1/bids/export/excel", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function exportBidPdf(payload: BidPreviewRequest): Promise<Blob> {
  return requestBlob("/api/v1/bids/export/pdf", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function parsePdf(payload: ParsePdfRequest): Promise<ParsePdfResponse> {
  return request<ParsePdfResponse>("/api/v1/parse/pdf", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("Failed to read file content"));
        return;
      }
      const commaIndex = reader.result.indexOf(",");
      resolve(commaIndex >= 0 ? reader.result.slice(commaIndex + 1) : reader.result);
    };
    reader.onerror = () => {
      reject(reader.error ?? new Error("Failed to read file"));
    };
    reader.readAsDataURL(file);
  });
}

export async function parsePdfUpload(file: File): Promise<ParsePdfResponse> {
  const payload: ParsePdfBase64Request = {
    file_name: file.name,
    file_bytes_base64: await fileToBase64(file),
  };
  try {
    return await request<ParsePdfResponse>("/api/v1/parse/pdf/base64", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  } catch (base64Err) {
    if (!isNotFoundError(base64Err)) {
      throw base64Err;
    }
  }

  const form = new FormData();
  form.append("file", file);
  try {
    return await request<ParsePdfResponse>("/api/v1/parse/pdf/upload", {
      method: "POST",
      body: form,
    });
  } catch (uploadErr) {
    if (!isNotFoundError(uploadErr)) {
      throw uploadErr;
    }
  }

  const nativePath = getNativeFilePath(file);
  if (nativePath) {
    return parsePdf({ pdf_file_path: nativePath });
  }

  throw new Error(
    "PDF upload route not found on running API. Restart the desktop app to load the latest API.",
  );
}

export function getDashboardSummary(): Promise<DashboardSummaryResponse> {
  return request<DashboardSummaryResponse>("/api/v1/dashboard/summary");
}

export function previewBidUpload(
  file: File,
  payload: BidPreviewUploadRequest,
): Promise<BidPreviewResponse> {
  return previewBidBase64(file, payload);
}

async function previewBidBase64(
  file: File,
  payload: BidPreviewUploadRequest,
): Promise<BidPreviewResponse> {
  const base64Payload: BidPreviewBase64Request = {
    file_name: file.name,
    pricing_file_base64: await fileToBase64(file),
    pricing_sheet: payload.pricing_sheet,
    compliance_code: payload.compliance_code || "DUAL",
    project_data: payload.project_data || {},
    workers: payload.workers || [],
  };
  try {
    return await request<BidPreviewResponse>("/api/v1/bids/preview/base64", {
      method: "POST",
      body: JSON.stringify(base64Payload),
    });
  } catch (base64Err) {
    if (!isNotFoundError(base64Err)) {
      throw base64Err;
    }
  }

  const form = new FormData();
  form.append("pricing_file", file);
  if (payload.pricing_sheet) {
    form.append("pricing_sheet", payload.pricing_sheet);
  }
  form.append("compliance_code", payload.compliance_code || "DUAL");
  form.append("project_data_json", JSON.stringify(payload.project_data || {}));
  form.append("workers_json", JSON.stringify(payload.workers || []));
  try {
    return await request<BidPreviewResponse>("/api/v1/bids/preview/upload", {
      method: "POST",
      body: form,
    });
  } catch (uploadErr) {
    if (!isNotFoundError(uploadErr)) {
      throw uploadErr;
    }
  }

  const nativePath = getNativeFilePath(file);
  if (nativePath) {
    return previewBid({
      pricing_file_path: nativePath,
      pricing_sheet: payload.pricing_sheet,
      compliance_code: payload.compliance_code,
      project_data: payload.project_data,
      workers: payload.workers,
    });
  }

  throw new Error(
    "Pricing upload route not found on running API. Restart the desktop app to load the latest API.",
  );
}

async function exportBidExcelBase64(file: File, payload: BidPreviewUploadRequest): Promise<Blob> {
  const base64Payload: BidPreviewBase64Request = {
    file_name: file.name,
    pricing_file_base64: await fileToBase64(file),
    pricing_sheet: payload.pricing_sheet,
    compliance_code: payload.compliance_code || "DUAL",
    project_data: payload.project_data || {},
    workers: payload.workers || [],
  };
  try {
    return await requestBlob("/api/v1/bids/export/excel/base64", {
      method: "POST",
      body: JSON.stringify(base64Payload),
    });
  } catch (base64Err) {
    if (!isNotFoundError(base64Err)) {
      throw base64Err;
    }
  }

  const nativePath = getNativeFilePath(file);
  if (nativePath) {
    return exportBidExcel({
      pricing_file_path: nativePath,
      pricing_sheet: payload.pricing_sheet,
      compliance_code: payload.compliance_code,
      project_data: payload.project_data,
      workers: payload.workers,
    });
  }

  throw new Error(
    "Excel export route not found on running API. Restart the desktop app to load the latest API.",
  );
}

async function exportBidPdfBase64(file: File, payload: BidPreviewUploadRequest): Promise<Blob> {
  const base64Payload: BidPreviewBase64Request = {
    file_name: file.name,
    pricing_file_base64: await fileToBase64(file),
    pricing_sheet: payload.pricing_sheet,
    compliance_code: payload.compliance_code || "DUAL",
    project_data: payload.project_data || {},
    workers: payload.workers || [],
  };
  try {
    return await requestBlob("/api/v1/bids/export/pdf/base64", {
      method: "POST",
      body: JSON.stringify(base64Payload),
    });
  } catch (base64Err) {
    if (!isNotFoundError(base64Err)) {
      throw base64Err;
    }
  }

  const nativePath = getNativeFilePath(file);
  if (nativePath) {
    return exportBidPdf({
      pricing_file_path: nativePath,
      pricing_sheet: payload.pricing_sheet,
      compliance_code: payload.compliance_code,
      project_data: payload.project_data,
      workers: payload.workers,
    });
  }

  throw new Error(
    "PDF export route not found on running API. Restart the desktop app to load the latest API.",
  );
}

export function exportBidExcelUpload(file: File, payload: BidPreviewUploadRequest): Promise<Blob> {
  return exportBidExcelBase64(file, payload);
}

export function exportBidPdfUpload(file: File, payload: BidPreviewUploadRequest): Promise<Blob> {
  return exportBidPdfBase64(file, payload);
}

export function getJobsBoard(): Promise<JobsBoardResponse> {
  return request<JobsBoardResponse>("/api/v1/jobs/board");
}

export function updateJobStatus(
  jobId: number,
  payload: JobStatusUpdateRequest,
): Promise<JobStatusUpdateResponse> {
  return request<JobStatusUpdateResponse>(`/api/v1/jobs/${jobId}/status`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function approveJob(jobId: number, payload: JobApproveRequest): Promise<JobApproveResponse> {
  return request<JobApproveResponse>(`/api/v1/jobs/${jobId}/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCalendarJobs(params: {
  start_date: string;
  end_date: string;
  status?: string;
  crew?: string;
}): Promise<CalendarJobsResponse> {
  const search = new URLSearchParams();
  search.set("start_date", params.start_date);
  search.set("end_date", params.end_date);
  if (params.status) {
    search.set("status", params.status);
  }
  if (params.crew) {
    search.set("crew", params.crew);
  }
  return request<CalendarJobsResponse>(`/api/v1/calendar/jobs?${search.toString()}`);
}

export function getCalendarDay(params: {
  date: string;
  status?: string;
  crew?: string;
}): Promise<CalendarDayResponse> {
  const search = new URLSearchParams();
  search.set("date", params.date);
  if (params.status) {
    search.set("status", params.status);
  }
  if (params.crew) {
    search.set("crew", params.crew);
  }
  return request<CalendarDayResponse>(`/api/v1/calendar/day?${search.toString()}`);
}
