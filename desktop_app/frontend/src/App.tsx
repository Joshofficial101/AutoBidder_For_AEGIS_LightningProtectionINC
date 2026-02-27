import { ChangeEvent, FormEvent, MouseEvent, useEffect, useRef, useState } from "react";
import {
  approveJob,
  exportBidExcel,
  exportBidExcelUpload,
  exportBidPdf,
  exportBidPdfUpload,
  getCalendarJobs,
  getDashboardSummary,
  getHealthReadiness,
  getJobsBoard,
  login,
  logoutSession,
  parsePdf,
  parsePdfUpload,
  previewBid,
  previewBidUpload,
  register,
  resetPasswordWithBackupCode,
  setAuthFailureHandler,
  setAuthToken,
  verifyPassword,
  updateJobStatus,
} from "./api/client";
import {
  AuthUser,
  BidPreviewResponse,
  CalendarJobItem,
  CalendarJobsResponse,
  DashboardJobItem,
  DashboardSummaryResponse,
  HealthReadinessResponse,
  JobBoardStatus,
  JobsBoardResponse,
} from "./api/types";

type NavKey = "dashboard" | "bidding" | "jobs" | "calendar" | "reports";

type WorkerInput = {
  name: string;
  wage_per_hour: string;
  hours: string;
};

type CalendarViewMode = "month" | "week" | "day";
type AlertLevel = "none" | "warning" | "overdue";

type JobsBoardColumnKey = Exclude<keyof JobsBoardResponse, "user_id">;
type WorkflowAlertSettings = {
  scheduled_to_start_days: number;
  in_progress_to_inspection_days: number;
  inspection_to_completed_days: number;
  completed_to_invoiced_days: number;
  warning_lead_days: number;
};
type WorkflowAlertSettingsField = keyof WorkflowAlertSettings;
type WorkflowAlertSettingsForm = Record<WorkflowAlertSettingsField, string>;
type WorkflowAlertJob = Pick<
  DashboardJobItem,
  "status" | "scheduled_date" | "start_date" | "completion_date"
>;
type BiddingProfileRoundingMode = "none" | "nearest" | "up" | "down";
type BiddingCustomPricingAdjustment = {
  adjustment_id: string;
  name: string;
  mode: "$" | "%";
  value: number;
};
type BiddingCustomPricingAdjustmentForm = {
  adjustment_id: string;
  name: string;
  mode: "$" | "%";
  value: string;
};
type BiddingProfileSettings = {
  labor_markup_pct: number;
  overhead_pct: number;
  profit_pct: number;
  commission_amount: number;
  tools_rental_amount: number;
  tools_rental_type: "$" | "%";
  shipping_amount: number;
  use_tax_pct: number;
  minimum_bid_amount: number;
  rounding_increment: number;
  rounding_mode: BiddingProfileRoundingMode;
  custom_pricing_adjustments: BiddingCustomPricingAdjustment[];
};
type BiddingProfileFormField =
  | "labor_markup_pct"
  | "overhead_pct"
  | "profit_pct"
  | "commission_amount"
  | "tools_rental_amount"
  | "tools_rental_type"
  | "shipping_amount"
  | "use_tax_pct"
  | "minimum_bid_amount"
  | "rounding_increment"
  | "rounding_mode";
type BiddingProfileForm = Record<BiddingProfileFormField, string>;
type NamedBiddingProfile = {
  profile_id: string;
  name: string;
  settings: BiddingProfileSettings;
  created_at: string;
  updated_at: string;
};
type BiddingProfileLibrary = {
  active_profile_id: string;
  profiles: NamedBiddingProfile[];
};

const WORKFLOW_ALERT_SETTINGS_STORAGE_PREFIX = "lightningbid.workflow_alert_settings.v1.user";
const BIDDING_PROFILES_STORAGE_PREFIX = "lightningbid.bidding_profiles.v1.user";
const LEGACY_BIDDING_PROFILE_STORAGE_PREFIX = "lightningbid.bidding_profile.v1.user";
const DEFAULT_WORKFLOW_ALERT_SETTINGS: WorkflowAlertSettings = {
  scheduled_to_start_days: 1,
  in_progress_to_inspection_days: 3,
  inspection_to_completed_days: 2,
  completed_to_invoiced_days: 7,
  warning_lead_days: 1,
};
const DEFAULT_BIDDING_PROFILE_SETTINGS: BiddingProfileSettings = {
  labor_markup_pct: 20,
  overhead_pct: 10,
  profit_pct: 10,
  commission_amount: 0,
  tools_rental_amount: 0,
  tools_rental_type: "$",
  shipping_amount: 0,
  use_tax_pct: 0,
  minimum_bid_amount: 0,
  rounding_increment: 100,
  rounding_mode: "nearest",
  custom_pricing_adjustments: [],
};
const DEFAULT_BIDDING_PROFILE_NAME = "Default";
const workflowAlertSettingFields: Array<{
  key: WorkflowAlertSettingsField;
  label: string;
  description: string;
  min: number;
  max: number;
}> = [
  {
    key: "scheduled_to_start_days",
    label: "Scheduled to In Progress",
    description: "Warn when a scheduled job has not started within this many days.",
    min: 0,
    max: 60,
  },
  {
    key: "in_progress_to_inspection_days",
    label: "In Progress to Inspection",
    description: "Warn when a job remains in progress past this many days.",
    min: 0,
    max: 120,
  },
  {
    key: "inspection_to_completed_days",
    label: "Inspection to Completed",
    description: "Warn when inspection is not closed out within this many days.",
    min: 0,
    max: 60,
  },
  {
    key: "completed_to_invoiced_days",
    label: "Completed to Invoiced",
    description: "Warn when completed work is not invoiced within this many days.",
    min: 0,
    max: 180,
  },
  {
    key: "warning_lead_days",
    label: "Warning Lead Time",
    description: "Show a warning this many days before each overdue threshold.",
    min: 0,
    max: 30,
  },
];

const navItems: Array<{ key: NavKey; label: string; icon: string }> = [
  { key: "dashboard", label: "Dashboard", icon: "DG" },
  { key: "bidding", label: "Bidding", icon: "BD" },
  { key: "jobs", label: "Jobs", icon: "JB" },
  { key: "calendar", label: "Calendar", icon: "CL" },
  { key: "reports", label: "Reports", icon: "RP" },
];

const jobsBoardColumns: Array<{
  key: JobsBoardColumnKey;
  label: string;
  emptyText: string;
  actionType?: "approve" | "advance";
  actionLabel?: string;
  nextStatus?: JobBoardStatus;
}> = [
  {
    key: "awaiting_approval",
    label: "Awaiting Approval",
    emptyText: "No jobs awaiting approval.",
    actionType: "approve",
    actionLabel: "Approve & Schedule",
    nextStatus: "scheduled",
  },
  {
    key: "scheduled",
    label: "Scheduled",
    emptyText: "No scheduled jobs.",
    actionType: "advance",
    actionLabel: "Move to In Progress",
    nextStatus: "in_progress",
  },
  {
    key: "in_progress",
    label: "In Progress",
    emptyText: "No jobs in progress.",
    actionType: "advance",
    actionLabel: "Move to Inspection",
    nextStatus: "inspection",
  },
  {
    key: "inspection",
    label: "Inspection",
    emptyText: "No jobs awaiting inspection.",
    actionType: "advance",
    actionLabel: "Mark Completed",
    nextStatus: "completed",
  },
  {
    key: "completed",
    label: "Completed",
    emptyText: "No completed jobs awaiting invoicing.",
    actionType: "advance",
    actionLabel: "Mark Invoiced",
    nextStatus: "invoiced",
  },
  {
    key: "invoiced",
    label: "Invoiced",
    emptyText: "No invoiced jobs yet.",
  },
];

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const calendarWeekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const AUTH_SESSION_KEY = "lightningbid.auth.user";
const AUTH_IDLE_TIMEOUT_MS = 30 * 60 * 1000;
const AUTH_MAX_SESSION_MS = 8 * 60 * 60 * 1000;
const AUTH_ACTIVITY_PERSIST_MS = 15 * 1000;
const AUTH_UPPER_PATTERN = /[A-Z]/;
const AUTH_LOWER_PATTERN = /[a-z]/;
const AUTH_DIGIT_PATTERN = /\d/;
const AUTH_SYMBOL_PATTERN = /[^A-Za-z0-9]/;
const AUTH_COMMON_WEAK_PASSWORDS = new Set([
  "password",
  "password123",
  "letmein",
  "qwerty",
  "qwerty123",
  "12345678",
  "123456789",
  "admin123",
  "welcome1",
]);

type AuthSessionState = {
  user: AuthUser;
  created_at: string;
  last_active_at: string;
  expires_at: string;
};

function buildAuthSession(user: AuthUser, nowMs: number = Date.now()): AuthSessionState {
  return {
    user,
    created_at: new Date(nowMs).toISOString(),
    last_active_at: new Date(nowMs).toISOString(),
    expires_at: new Date(nowMs + AUTH_IDLE_TIMEOUT_MS).toISOString(),
  };
}

function parseTimestamp(value: unknown): number | null {
  if (typeof value !== "string") {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseAuthSession(raw: string | null): AuthSessionState | null {
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }

    const parsedObj = parsed as Record<string, unknown>;
    const parsedSessionUser = parsedObj.user as Record<string, unknown> | undefined;
    if (
      parsedSessionUser &&
      typeof parsedSessionUser.user_id === "number" &&
      typeof parsedSessionUser.username === "string" &&
      typeof parsedSessionUser.access_token === "string" &&
      typeof parsedSessionUser.token_type === "string" &&
      typeof parsedSessionUser.expires_at === "string"
    ) {
      const session = parsed as AuthSessionState;
      const created = parseTimestamp(session.created_at);
      const lastActive = parseTimestamp(session.last_active_at);
      const expires = parseTimestamp(session.expires_at);
      if (created !== null && lastActive !== null && expires !== null) {
        return session;
      }
    }
  } catch {
    return null;
  }

  return null;
}

function isAuthSessionExpired(session: AuthSessionState, nowMs: number = Date.now()): boolean {
  const createdAtMs = parseTimestamp(session.created_at);
  const lastActiveAtMs = parseTimestamp(session.last_active_at);
  const expiresAtMs = parseTimestamp(session.expires_at);
  if (createdAtMs === null || lastActiveAtMs === null || expiresAtMs === null) {
    return true;
  }
  if (nowMs > expiresAtMs) {
    return true;
  }
  if (nowMs - lastActiveAtMs > AUTH_IDLE_TIMEOUT_MS) {
    return true;
  }
  return nowMs - createdAtMs > AUTH_MAX_SESSION_MS;
}

function withSessionActivity(session: AuthSessionState, nowMs: number = Date.now()): AuthSessionState {
  const createdAtMs = parseTimestamp(session.created_at) ?? nowMs;
  const maxExpiryMs = createdAtMs + AUTH_MAX_SESSION_MS;
  return {
    ...session,
    last_active_at: new Date(nowMs).toISOString(),
    expires_at: new Date(Math.min(maxExpiryMs, nowMs + AUTH_IDLE_TIMEOUT_MS)).toISOString(),
  };
}

function readAuthSessionFromStorage(): AuthSessionState | null {
  const sessionRaw = window.sessionStorage.getItem(AUTH_SESSION_KEY);
  if (sessionRaw) {
    return parseAuthSession(sessionRaw);
  }

  // Cleanup: remove any older persisted auth session so launch requires sign-in.
  window.localStorage.removeItem(AUTH_SESSION_KEY);
  return null;
}

function writeAuthSessionToStorage(session: AuthSessionState): void {
  window.sessionStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));
}

function clearAuthSessionFromStorage(): void {
  window.localStorage.removeItem(AUTH_SESSION_KEY);
  window.sessionStorage.removeItem(AUTH_SESSION_KEY);
}

type PasswordStrengthLevel = "weak" | "medium" | "strong";

type PasswordRuleStatus = {
  label: string;
  met: boolean;
};

function evaluatePasswordRules(
  password: string,
  username: string,
  email: string,
): { rules: PasswordRuleStatus[]; level: PasswordStrengthLevel; score: number; progress: number } {
  const trimmedUsername = username.trim().toLowerCase();
  const trimmedEmailLocal = email.trim().toLowerCase().split("@", 1)[0];
  const loweredPassword = password.toLowerCase();
  const lengthOk = password.length >= 12 && password.length <= 128;

  const rules: PasswordRuleStatus[] = [
    { label: "12+ characters", met: lengthOk },
    { label: "At least 1 uppercase letter", met: AUTH_UPPER_PATTERN.test(password) },
    { label: "At least 1 lowercase letter", met: AUTH_LOWER_PATTERN.test(password) },
    { label: "At least 1 number", met: AUTH_DIGIT_PATTERN.test(password) },
    { label: "At least 1 symbol", met: AUTH_SYMBOL_PATTERN.test(password) },
    { label: "No spaces", met: !/\s/.test(password) },
    {
      label: "Does not include username/email",
      met:
        (!trimmedUsername || !loweredPassword.includes(trimmedUsername)) &&
        (!trimmedEmailLocal || !loweredPassword.includes(trimmedEmailLocal)),
    },
    { label: "Not a common password", met: !AUTH_COMMON_WEAK_PASSWORDS.has(loweredPassword) },
  ];

  const score = rules.reduce((acc, rule) => acc + (rule.met ? 1 : 0), 0);
  const hasValue = password.length > 0;

  let level: PasswordStrengthLevel = "weak";
  if (!hasValue || score <= 4) {
    level = "weak";
  } else if (score <= 6) {
    level = "medium";
  } else {
    level = "strong";
  }

  const progress =
    level === "weak"
      ? hasValue
        ? 34
        : 0
      : level === "medium"
        ? 68
        : 100;

  return { rules, level, score, progress };
}

type RecoveryPacketContext = "account_created" | "password_reset";

type RecoveryPacket = {
  username: string;
  backupCode: string;
  context: RecoveryPacketContext;
};

function sanitizeFileName(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, "_");
}

function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function downloadRecoveryTxt(packet: RecoveryPacket): void {
  const lines = [
    "LightningBid Backup Recovery Code",
    "================================",
    `Username: ${packet.username}`,
    `Backup Code: ${packet.backupCode}`,
    `Issued: ${new Date().toLocaleString()}`,
    "",
    "Store this code in a secure place. Keep it private.",
    "Use this code to reset your password if you forget it.",
  ];
  downloadBlob(
    `lightningbid_backup_code_${sanitizeFileName(packet.username)}.txt`,
    new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" }),
  );
}

function escapePdfText(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

function buildSimplePdf(lines: string[]): Uint8Array {
  const encoder = new TextEncoder();
  const streamParts: string[] = ["BT", "/F1 12 Tf", "48 790 Td", "16 TL"];
  lines.forEach((line, index) => {
    if (index > 0) {
      streamParts.push("T*");
    }
    streamParts.push(`(${escapePdfText(line)}) Tj`);
  });
  streamParts.push("ET");
  const streamContent = `${streamParts.join("\n")}\n`;
  const streamLength = encoder.encode(streamContent).length;

  const objects = [
    "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
    "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
    `4 0 obj\n<< /Length ${streamLength} >>\nstream\n${streamContent}endstream\nendobj\n`,
    "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
  ];

  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [0];
  objects.forEach((obj) => {
    offsets.push(encoder.encode(pdf).length);
    pdf += obj;
  });

  const xrefOffset = encoder.encode(pdf).length;
  pdf += `xref\n0 ${objects.length + 1}\n`;
  pdf += "0000000000 65535 f \n";
  for (let i = 1; i < offsets.length; i += 1) {
    pdf += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;

  return encoder.encode(pdf);
}

function downloadRecoveryPdf(packet: RecoveryPacket): void {
  const lines = [
    "LightningBid Backup Recovery Code",
    "",
    `Username: ${packet.username}`,
    `Backup Code: ${packet.backupCode}`,
    `Issued: ${new Date().toLocaleString()}`,
    "",
    "Store this code in a secure place.",
    "Do not share it with anyone.",
  ];

  const pdfBytes = buildSimplePdf(lines);
  downloadBlob(
    `lightningbid_backup_code_${sanitizeFileName(packet.username)}.pdf`,
    new Blob([pdfBytes as unknown as BlobPart], { type: "application/pdf" }),
  );
}

function printRecoveryPacket(packet: RecoveryPacket): void {
  const printWindow = window.open("", "_blank", "noopener,noreferrer,width=760,height=900");
  if (!printWindow) {
    return;
  }
  const issuedText = new Date().toLocaleString();
  printWindow.document.write(`<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>LightningBid Backup Code</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 32px; color: #102033; }
      h1 { margin: 0 0 12px; font-size: 20px; }
      .box { border: 1px solid #9fb7d4; border-radius: 10px; padding: 14px; }
      .code { font-size: 24px; letter-spacing: 1px; font-weight: 700; margin: 10px 0; }
      p { margin: 8px 0; }
    </style>
  </head>
  <body>
    <h1>LightningBid Backup Recovery Code</h1>
    <div class="box">
      <p><strong>Username:</strong> ${packet.username}</p>
      <p class="code">${packet.backupCode}</p>
      <p><strong>Issued:</strong> ${issuedText}</p>
      <p>Store this in a secure place and do not share it.</p>
    </div>
  </body>
</html>`);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}

function toNumber(value: string): number | undefined {
  if (!value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "N/A";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString();
}

function toIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function fromIsoDate(value: string): Date {
  const [year, month, day] = value.split("-").map((part) => Number(part));
  return new Date(year, (month || 1) - 1, day || 1);
}

function addDays(value: Date, days: number): Date {
  const next = new Date(value.getFullYear(), value.getMonth(), value.getDate());
  next.setDate(next.getDate() + days);
  return next;
}

function startOfWeek(value: Date): Date {
  const day = (value.getDay() + 6) % 7; // Monday = 0
  return addDays(value, -day);
}

function endOfWeek(value: Date): Date {
  return addDays(startOfWeek(value), 6);
}

function startOfMonth(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), 1);
}

function endOfMonth(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth() + 1, 0);
}

function normalizeJobDate(value?: string | null): string | null {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const isoPrefix = trimmed.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(isoPrefix)) {
    return isoPrefix;
  }

  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return toIsoDate(parsed);
}

function alertSettingsStorageKey(userId: number): string {
  return `${WORKFLOW_ALERT_SETTINGS_STORAGE_PREFIX}.${userId}`;
}

function alertSettingsToFormValues(settings: WorkflowAlertSettings): WorkflowAlertSettingsForm {
  return {
    scheduled_to_start_days: String(settings.scheduled_to_start_days),
    in_progress_to_inspection_days: String(settings.in_progress_to_inspection_days),
    inspection_to_completed_days: String(settings.inspection_to_completed_days),
    completed_to_invoiced_days: String(settings.completed_to_invoiced_days),
    warning_lead_days: String(settings.warning_lead_days),
  };
}

function parseAlertSettingValue(raw: unknown, fallback: number): number {
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(0, Math.floor(parsed));
}

function normalizeWorkflowAlertSettings(raw: unknown): WorkflowAlertSettings {
  if (!raw || typeof raw !== "object") {
    return DEFAULT_WORKFLOW_ALERT_SETTINGS;
  }

  const value = raw as Partial<Record<WorkflowAlertSettingsField, unknown>>;
  return {
    scheduled_to_start_days: parseAlertSettingValue(
      value.scheduled_to_start_days,
      DEFAULT_WORKFLOW_ALERT_SETTINGS.scheduled_to_start_days,
    ),
    in_progress_to_inspection_days: parseAlertSettingValue(
      value.in_progress_to_inspection_days,
      DEFAULT_WORKFLOW_ALERT_SETTINGS.in_progress_to_inspection_days,
    ),
    inspection_to_completed_days: parseAlertSettingValue(
      value.inspection_to_completed_days,
      DEFAULT_WORKFLOW_ALERT_SETTINGS.inspection_to_completed_days,
    ),
    completed_to_invoiced_days: parseAlertSettingValue(
      value.completed_to_invoiced_days,
      DEFAULT_WORKFLOW_ALERT_SETTINGS.completed_to_invoiced_days,
    ),
    warning_lead_days: parseAlertSettingValue(
      value.warning_lead_days,
      DEFAULT_WORKFLOW_ALERT_SETTINGS.warning_lead_days,
    ),
  };
}

function readWorkflowAlertSettings(userId: number): WorkflowAlertSettings {
  try {
    const raw = window.localStorage.getItem(alertSettingsStorageKey(userId));
    if (!raw) {
      return DEFAULT_WORKFLOW_ALERT_SETTINGS;
    }
    return normalizeWorkflowAlertSettings(JSON.parse(raw));
  } catch {
    return DEFAULT_WORKFLOW_ALERT_SETTINGS;
  }
}

function writeWorkflowAlertSettings(userId: number, settings: WorkflowAlertSettings): void {
  try {
    window.localStorage.setItem(
      alertSettingsStorageKey(userId),
      JSON.stringify(normalizeWorkflowAlertSettings(settings)),
    );
  } catch {
    // Keep silent; alert settings can still be used for the current session.
  }
}

function workflowAlertLevelClass(level: AlertLevel): string {
  return level === "none" ? "" : ` sla-${level}`;
}

function workflowAlertLabel(level: AlertLevel): string {
  if (level === "overdue") {
    return "SLA Overdue";
  }
  if (level === "warning") {
    return "SLA Warning";
  }
  return "";
}

function workflowAlertBaseDate(job: WorkflowAlertJob): string | null {
  if (job.status === "scheduled") {
    return normalizeJobDate(job.scheduled_date);
  }
  if (job.status === "in_progress") {
    return normalizeJobDate(job.start_date) ?? normalizeJobDate(job.scheduled_date);
  }
  if (job.status === "inspection") {
    return normalizeJobDate(job.completion_date) ?? normalizeJobDate(job.start_date);
  }
  if (job.status === "completed") {
    return normalizeJobDate(job.completion_date);
  }
  return null;
}

function workflowAlertThresholdDays(status: string, settings: WorkflowAlertSettings): number | null {
  if (status === "scheduled") {
    return settings.scheduled_to_start_days;
  }
  if (status === "in_progress") {
    return settings.in_progress_to_inspection_days;
  }
  if (status === "inspection") {
    return settings.inspection_to_completed_days;
  }
  if (status === "completed") {
    return settings.completed_to_invoiced_days;
  }
  return null;
}

function daysBetween(from: Date, to: Date): number {
  const fromUtc = Date.UTC(from.getFullYear(), from.getMonth(), from.getDate());
  const toUtc = Date.UTC(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.floor((toUtc - fromUtc) / (24 * 60 * 60 * 1000));
}

function evaluateWorkflowAlert(
  job: WorkflowAlertJob,
  settings: WorkflowAlertSettings,
  now: Date = new Date(),
): AlertLevel {
  const thresholdDays = workflowAlertThresholdDays(job.status, settings);
  if (thresholdDays === null) {
    return "none";
  }

  const baseDate = workflowAlertBaseDate(job);
  if (!baseDate) {
    return "none";
  }

  const elapsedDays = daysBetween(fromIsoDate(baseDate), now);
  if (elapsedDays >= thresholdDays) {
    return "overdue";
  }

  const warningThreshold = Math.max(0, thresholdDays - settings.warning_lead_days);
  if (elapsedDays >= warningThreshold) {
    return "warning";
  }

  return "none";
}

function biddingProfilesStorageKey(userId: number): string {
  return `${BIDDING_PROFILES_STORAGE_PREFIX}.${userId}`;
}

function legacyBiddingProfileStorageKey(userId: number): string {
  return `${LEGACY_BIDDING_PROFILE_STORAGE_PREFIX}.${userId}`;
}

function createProfileId(): string {
  return `profile_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function createCustomAdjustmentId(): string {
  return `adj_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function normalizeProfileName(value: string): string {
  const trimmed = value.trim();
  return trimmed || DEFAULT_BIDDING_PROFILE_NAME;
}

function buildNamedProfile(name: string, settings: BiddingProfileSettings): NamedBiddingProfile {
  const now = new Date().toISOString();
  return {
    profile_id: createProfileId(),
    name: normalizeProfileName(name),
    settings: normalizeBiddingProfile(settings),
    created_at: now,
    updated_at: now,
  };
}

function biddingProfileToFormValues(settings: BiddingProfileSettings): BiddingProfileForm {
  return {
    labor_markup_pct: String(settings.labor_markup_pct),
    overhead_pct: String(settings.overhead_pct),
    profit_pct: String(settings.profit_pct),
    commission_amount: String(settings.commission_amount),
    tools_rental_amount: String(settings.tools_rental_amount),
    tools_rental_type: settings.tools_rental_type,
    shipping_amount: String(settings.shipping_amount),
    use_tax_pct: String(settings.use_tax_pct),
    minimum_bid_amount: String(settings.minimum_bid_amount),
    rounding_increment: String(settings.rounding_increment),
    rounding_mode: settings.rounding_mode,
  };
}

function parseNumberWithFallback(raw: unknown, fallback: number): number {
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return parsed;
}

function normalizeBiddingProfile(raw: unknown): BiddingProfileSettings {
  if (!raw || typeof raw !== "object") {
    return DEFAULT_BIDDING_PROFILE_SETTINGS;
  }

  const value = raw as Partial<{
    labor_markup_pct: unknown;
    overhead_pct: unknown;
    profit_pct: unknown;
    commission_amount: unknown;
    tools_rental_amount: unknown;
    tools_rental_type: unknown;
    shipping_amount: unknown;
    use_tax_pct: unknown;
    minimum_bid_amount: unknown;
    rounding_increment: unknown;
    rounding_mode: unknown;
    custom_pricing_adjustments: unknown;
  }>;
  const toolsRentalType = value.tools_rental_type === "%" ? "%" : "$";
  const roundingMode = (() => {
    if (value.rounding_mode === "nearest" || value.rounding_mode === "up" || value.rounding_mode === "down") {
      return value.rounding_mode;
    }
    return "none";
  })();
  const customAdjustmentsRaw = Array.isArray(value.custom_pricing_adjustments)
    ? value.custom_pricing_adjustments
    : [];
  const customPricingAdjustments: BiddingCustomPricingAdjustment[] = customAdjustmentsRaw
    .map((candidate) => {
      if (!candidate || typeof candidate !== "object") {
        return null;
      }
      const parsed = candidate as Partial<{
        adjustment_id: unknown;
        name: unknown;
        mode: unknown;
        value: unknown;
      }>;
      const name = String(parsed.name ?? "").trim();
      if (!name) {
        return null;
      }
      const numericValue = parseNumberWithFallback(parsed.value, 0);
      const mode = parsed.mode === "%" ? "%" : "$";
      const adjustmentId =
        typeof parsed.adjustment_id === "string" && parsed.adjustment_id.trim()
          ? parsed.adjustment_id.trim()
          : createCustomAdjustmentId();
      return {
        adjustment_id: adjustmentId,
        name,
        mode,
        value: Math.max(0, numericValue),
      } satisfies BiddingCustomPricingAdjustment;
    })
    .filter((value): value is BiddingCustomPricingAdjustment => value !== null);

  return {
    labor_markup_pct: parseNumberWithFallback(
      value.labor_markup_pct,
      DEFAULT_BIDDING_PROFILE_SETTINGS.labor_markup_pct,
    ),
    overhead_pct: parseNumberWithFallback(
      value.overhead_pct,
      DEFAULT_BIDDING_PROFILE_SETTINGS.overhead_pct,
    ),
    profit_pct: parseNumberWithFallback(
      value.profit_pct,
      DEFAULT_BIDDING_PROFILE_SETTINGS.profit_pct,
    ),
    commission_amount: parseNumberWithFallback(
      value.commission_amount,
      DEFAULT_BIDDING_PROFILE_SETTINGS.commission_amount,
    ),
    tools_rental_amount: parseNumberWithFallback(
      value.tools_rental_amount,
      DEFAULT_BIDDING_PROFILE_SETTINGS.tools_rental_amount,
    ),
    tools_rental_type: toolsRentalType,
    shipping_amount: parseNumberWithFallback(
      value.shipping_amount,
      DEFAULT_BIDDING_PROFILE_SETTINGS.shipping_amount,
    ),
    use_tax_pct: parseNumberWithFallback(
      value.use_tax_pct,
      DEFAULT_BIDDING_PROFILE_SETTINGS.use_tax_pct,
    ),
    minimum_bid_amount: Math.max(
      0,
      parseNumberWithFallback(
        value.minimum_bid_amount,
        DEFAULT_BIDDING_PROFILE_SETTINGS.minimum_bid_amount,
      ),
    ),
    rounding_increment: Math.max(
      0,
      parseNumberWithFallback(
        value.rounding_increment,
        DEFAULT_BIDDING_PROFILE_SETTINGS.rounding_increment,
      ),
    ),
    rounding_mode: roundingMode,
    custom_pricing_adjustments: customPricingAdjustments,
  };
}

function settingsToCustomAdjustmentForms(
  settings: BiddingProfileSettings,
): BiddingCustomPricingAdjustmentForm[] {
  return settings.custom_pricing_adjustments.map((item) => ({
    adjustment_id: item.adjustment_id,
    name: item.name,
    mode: item.mode,
    value: String(item.value),
  }));
}

function defaultBiddingProfileLibrary(): BiddingProfileLibrary {
  const profile = buildNamedProfile(DEFAULT_BIDDING_PROFILE_NAME, DEFAULT_BIDDING_PROFILE_SETTINGS);
  return {
    active_profile_id: profile.profile_id,
    profiles: [profile],
  };
}

function normalizeBiddingProfileLibrary(raw: unknown): BiddingProfileLibrary {
  if (!raw || typeof raw !== "object") {
    return defaultBiddingProfileLibrary();
  }

  const parsed = raw as {
    active_profile_id?: unknown;
    profiles?: Array<{
      profile_id?: unknown;
      name?: unknown;
      settings?: unknown;
      created_at?: unknown;
      updated_at?: unknown;
    }>;
  };

  const normalizedProfiles: NamedBiddingProfile[] = [];
  const seenIds = new Set<string>();
  for (const candidate of parsed.profiles ?? []) {
    if (!candidate || typeof candidate !== "object") {
      continue;
    }

    const profileId =
      typeof candidate.profile_id === "string" && candidate.profile_id.trim()
        ? candidate.profile_id.trim()
        : createProfileId();
    if (seenIds.has(profileId)) {
      continue;
    }
    seenIds.add(profileId);

    normalizedProfiles.push({
      profile_id: profileId,
      name: normalizeProfileName(typeof candidate.name === "string" ? candidate.name : ""),
      settings: normalizeBiddingProfile(candidate.settings),
      created_at:
        typeof candidate.created_at === "string" && candidate.created_at.trim()
          ? candidate.created_at
          : new Date().toISOString(),
      updated_at:
        typeof candidate.updated_at === "string" && candidate.updated_at.trim()
          ? candidate.updated_at
          : new Date().toISOString(),
    });
  }

  if (normalizedProfiles.length === 0) {
    return defaultBiddingProfileLibrary();
  }

  const activeProfileId =
    typeof parsed.active_profile_id === "string" && parsed.active_profile_id.trim()
      ? parsed.active_profile_id.trim()
      : normalizedProfiles[0].profile_id;

  const activeExists = normalizedProfiles.some((profile) => profile.profile_id === activeProfileId);
  return {
    active_profile_id: activeExists ? activeProfileId : normalizedProfiles[0].profile_id,
    profiles: normalizedProfiles,
  };
}

function getActiveBiddingProfile(library: BiddingProfileLibrary): NamedBiddingProfile {
  const active = library.profiles.find((profile) => profile.profile_id === library.active_profile_id);
  return active ?? library.profiles[0];
}

function readLegacyBiddingProfile(userId: number): BiddingProfileSettings | null {
  try {
    const raw = window.localStorage.getItem(legacyBiddingProfileStorageKey(userId));
    if (!raw) {
      return null;
    }
    return normalizeBiddingProfile(JSON.parse(raw));
  } catch {
    return null;
  }
}

function readBiddingProfileLibrary(userId: number): BiddingProfileLibrary {
  try {
    const raw = window.localStorage.getItem(biddingProfilesStorageKey(userId));
    if (raw) {
      return normalizeBiddingProfileLibrary(JSON.parse(raw));
    }
  } catch {
    // Fall through to migration/default.
  }

  const legacy = readLegacyBiddingProfile(userId);
  if (legacy) {
    const migrated = {
      active_profile_id: "migrated_default",
      profiles: [
        {
          profile_id: "migrated_default",
          name: DEFAULT_BIDDING_PROFILE_NAME,
          settings: legacy,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
    };
    const normalized = normalizeBiddingProfileLibrary(migrated);
    writeBiddingProfileLibrary(userId, normalized);
    return normalized;
  }

  return defaultBiddingProfileLibrary();
}

function writeBiddingProfileLibrary(userId: number, library: BiddingProfileLibrary): void {
  try {
    window.localStorage.setItem(
      biddingProfilesStorageKey(userId),
      JSON.stringify(normalizeBiddingProfileLibrary(library)),
    );
  } catch {
    // Keep silent; local persistence is a convenience only.
  }
}

function jobDateKeys(job: CalendarJobItem): string[] {
  const keys = [
    normalizeJobDate(job.scheduled_date),
    normalizeJobDate(job.start_date),
    normalizeJobDate(job.completion_date),
  ].filter((value): value is string => Boolean(value));

  return Array.from(new Set(keys));
}

function calendarRange(currentDate: Date, viewMode: CalendarViewMode): { start: string; end: string } {
  if (viewMode === "week") {
    return { start: toIsoDate(startOfWeek(currentDate)), end: toIsoDate(endOfWeek(currentDate)) };
  }
  if (viewMode === "day") {
    const day = toIsoDate(currentDate);
    return { start: day, end: day };
  }
  return { start: toIsoDate(startOfMonth(currentDate)), end: toIsoDate(endOfMonth(currentDate)) };
}

function getNativeFilePath(file: File): string | null {
  const candidate = (file as File & { path?: string }).path;
  if (typeof candidate === "string" && candidate.trim()) {
    return candidate.trim();
  }
  return null;
}

function looksLikeFilePath(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) {
    return false;
  }
  return /^[a-zA-Z]:[\\/]/.test(trimmed) || trimmed.startsWith("\\\\") || trimmed.includes("/");
}

type AuthNetworkNode = {
  x: number;
  y: number;
  r: number;
  delay: number;
  spark?: boolean;
};

const authNetworkNodes: AuthNetworkNode[] = [
  { x: 8, y: 18, r: 0.9, delay: 0.3 },
  { x: 16, y: 30, r: 0.7, delay: 1.1, spark: true },
  { x: 24, y: 16, r: 1.1, delay: 2.7 },
  { x: 31, y: 39, r: 0.8, delay: 1.6 },
  { x: 41, y: 22, r: 0.85, delay: 0.8 },
  { x: 50, y: 34, r: 1.25, delay: 2.1, spark: true },
  { x: 60, y: 18, r: 0.85, delay: 3.1 },
  { x: 67, y: 41, r: 0.75, delay: 1.4 },
  { x: 76, y: 27, r: 0.95, delay: 2.5 },
  { x: 88, y: 16, r: 1.05, delay: 0.2, spark: true },
  { x: 13, y: 58, r: 0.75, delay: 2.9 },
  { x: 27, y: 66, r: 1.15, delay: 1.2, spark: true },
  { x: 42, y: 55, r: 0.8, delay: 3.4 },
  { x: 56, y: 69, r: 0.95, delay: 2.2 },
  { x: 72, y: 61, r: 0.8, delay: 0.6 },
  { x: 86, y: 73, r: 1.2, delay: 1.9, spark: true },
];

const authNetworkEdges: Array<[number, number]> = [
  [0, 1],
  [1, 3],
  [2, 4],
  [4, 5],
  [5, 7],
  [6, 8],
  [8, 9],
  [3, 5],
  [5, 8],
  [10, 11],
  [11, 12],
  [12, 13],
  [13, 14],
  [14, 15],
  [3, 11],
  [5, 12],
  [7, 14],
  [8, 14],
];

const authStrikePaths: Array<{ points: string; delay: number }> = [
  { points: "12,4 18,16 15,16 24,33 20,33 31,55 27,55 35,74", delay: 0.5 },
  { points: "56,3 62,15 58,15 67,30 63,30 74,52 69,52 80,73", delay: 2.7 },
  { points: "83,7 88,18 85,18 92,34 88,34 95,54 91,54 97,74", delay: 4.3 },
];

function AuthNetworkBackground() {
  return (
    <div className="auth-network-bg" aria-hidden="true">
      <svg className="auth-network-svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
        <g className="auth-protection-layer">
          <polyline className="auth-roof-line" points="4,84 17,73 33,73 50,66 67,73 83,73 96,84" />
          <line className="auth-ground-line" x1="3" y1="89" x2="97" y2="89" />
          <line className="auth-terminal" x1="17" y1="73" x2="17" y2="66" />
          <line className="auth-terminal" x1="50" y1="66" x2="50" y2="58" />
          <line className="auth-terminal" x1="83" y1="73" x2="83" y2="66" />
          <line className="auth-down-conductor" x1="17" y1="73" x2="17" y2="89" />
          <line className="auth-down-conductor" x1="83" y1="73" x2="83" y2="89" />
        </g>

        {authNetworkEdges.map(([from, to], index) => (
          <line
            key={`line-${from}-${to}-${index}`}
            className="auth-network-line"
            x1={authNetworkNodes[from].x}
            y1={authNetworkNodes[from].y}
            x2={authNetworkNodes[to].x}
            y2={authNetworkNodes[to].y}
          />
        ))}
        {authNetworkNodes.map((node, index) => (
          <circle
            key={`node-${index}`}
            className={`auth-network-node${node.spark ? " spark" : ""}`}
            cx={node.x}
            cy={node.y}
            r={node.r}
            style={{ animationDelay: `${node.delay}s` }}
          />
        ))}
        {authStrikePaths.map((strike, index) => (
          <polyline
            key={`strike-${index}`}
            className="auth-lightning-strike"
            points={strike.points}
            style={{ animationDelay: `${strike.delay}s` }}
          />
        ))}
        {authStrikePaths.map((strike, index) => (
          <polyline
            key={`strike-core-${index}`}
            className="auth-lightning-strike core"
            points={strike.points}
            style={{ animationDelay: `${strike.delay}s` }}
          />
        ))}
      </svg>
    </div>
  );
}

function AuthView({
  onAuthenticated,
  sessionNotice,
}: {
  onAuthenticated: (user: AuthUser) => void;
  sessionNotice?: string | null;
}) {
  const [mode, setMode] = useState<"signin" | "register" | "reset">("signin");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [backupCodeInput, setBackupCodeInput] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [recoveryPacket, setRecoveryPacket] = useState<RecoveryPacket | null>(null);
  const [pendingAuthUser, setPendingAuthUser] = useState<AuthUser | null>(null);

  const registerPasswordStrength = evaluatePasswordRules(password, username, email);
  const resetPasswordStrength = evaluatePasswordRules(newPassword, username, email);

  const authTitle =
    mode === "register" ? "Create Account" : mode === "reset" ? "Reset Password" : "Sign In";
  const authDescription =
    mode === "reset"
      ? "Use your backup recovery code to set a new password."
      : null;
  const sanitizeAuthUser = (user: AuthUser): AuthUser => ({
    user_id: user.user_id,
    username: user.username,
    access_token: user.access_token,
    token_type: user.token_type,
    expires_at: user.expires_at,
  });

  const clearAuthFeedback = () => {
    setError(null);
    setSuccess(null);
  };

  const switchMode = (nextMode: "signin" | "register" | "reset") => {
    setMode(nextMode);
    clearAuthFeedback();
    setRecoveryPacket(null);
    setPendingAuthUser(null);
    setPassword("");
    setBackupCodeInput("");
    setNewPassword("");
  };

  const handleContinueAfterBackupSaved = () => {
    if (pendingAuthUser) {
      onAuthenticated(sanitizeAuthUser(pendingAuthUser));
    }
    setRecoveryPacket(null);
    setPendingAuthUser(null);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSuccess(null);

    try {
      const trimmedUsername = username.trim();
      const trimmedEmail = email.trim();

      if (mode === "signin") {
        const user = await login({ username: trimmedUsername, password });
        setPassword("");
        onAuthenticated(sanitizeAuthUser(user));
        return;
      }

      if (mode === "register") {
        const user = await register({ username: trimmedUsername, email: trimmedEmail, password });
        setPassword("");

        if (user.backup_code) {
          setPendingAuthUser(sanitizeAuthUser(user));
          setRecoveryPacket({
            username: user.username,
            backupCode: user.backup_code,
            context: "account_created",
          });
          setSuccess("Account created. Save this backup code before continuing.");
          return;
        }

        onAuthenticated(sanitizeAuthUser(user));
        return;
      }

      const resetResult = await resetPasswordWithBackupCode({
        username: trimmedUsername,
        backup_code: backupCodeInput.trim().toUpperCase(),
        new_password: newPassword,
      });
      setBackupCodeInput("");
      setNewPassword("");
      if (resetResult.backup_code) {
        setRecoveryPacket({
          username: resetResult.username,
          backupCode: resetResult.backup_code,
          context: "password_reset",
        });
      }
      setSuccess("Password reset complete. Save your new backup code.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="auth-shell">
      <article className="panel auth-card">
        <h2>{authTitle}</h2>
        {authDescription ? <p>{authDescription}</p> : null}
        {sessionNotice ? <p className="auth-expired-note">{sessionNotice}</p> : null}

        {recoveryPacket ? (
          <div className="recovery-code-panel">
            <p className="recovery-code-title">
              {recoveryPacket.context === "account_created"
                ? "Backup code generated for your new account."
                : "Password reset complete. New backup code generated."}
            </p>
            <p className="recovery-code-username"><strong>User:</strong> {recoveryPacket.username}</p>
            <p className="recovery-code-value">{recoveryPacket.backupCode}</p>
            <p className="recovery-code-note">
              Save and print this code now. It is shown one time and should be kept private.
            </p>

            <div className="recovery-code-actions">
              <button
                className="nav-item"
                type="button"
                onClick={() => downloadRecoveryTxt(recoveryPacket)}
              >
                Save TXT
              </button>
              <button
                className="nav-item"
                type="button"
                onClick={() => downloadRecoveryPdf(recoveryPacket)}
              >
                Save PDF
              </button>
              <button
                className="nav-item"
                type="button"
                onClick={() => printRecoveryPacket(recoveryPacket)}
              >
                Print
              </button>
            </div>

            {recoveryPacket.context === "account_created" ? (
              <button
                className="nav-item primary-action"
                type="button"
                onClick={handleContinueAfterBackupSaved}
              >
                I Saved It, Continue
              </button>
            ) : (
              <button
                className="nav-item primary-action"
                type="button"
                onClick={() => switchMode("signin")}
              >
                Back to Sign In
              </button>
            )}
          </div>
        ) : (
          <>
            <form className="auth-form" onSubmit={submit}>
              <label>
                Username
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  required
                />
              </label>

              {mode === "register" ? (
                <label>
                  Email
                  <input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                    required
                  />
                </label>
              ) : null}

              {mode === "signin" || mode === "register" ? (
                <label>
                  Password
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={mode === "register" ? "new-password" : "current-password"}
                    required
                  />
                </label>
              ) : null}

              {mode === "reset" ? (
                <>
                  <label>
                    Backup Code
                    <input
                      value={backupCodeInput}
                      onChange={(e) => setBackupCodeInput(e.target.value.toUpperCase())}
                      placeholder="XXXX-XXXX-XXXX-XXXX"
                      autoComplete="off"
                      required
                    />
                  </label>
                  <label>
                    New Password
                    <input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      autoComplete="new-password"
                      required
                    />
                  </label>
                </>
              ) : null}

              {mode === "register" || mode === "reset" ? (
                <p className="auth-password-helper">Use 12+ chars with upper/lower/number/symbol.</p>
              ) : null}

              {mode === "register" || mode === "reset" ? (
                <div className="password-strength-box">
                  <div className="password-strength-head">
                    <strong>Password strength</strong>
                    <span
                      className={`strength-tag ${
                        mode === "register" ? registerPasswordStrength.level : resetPasswordStrength.level
                      }`}
                    >
                      {(
                        mode === "register" ? registerPasswordStrength.level : resetPasswordStrength.level
                      ).replace(/^./, (char) => char.toUpperCase())}
                    </span>
                  </div>
                  <div className="password-strength-track" aria-hidden="true">
                    <div
                      className={`password-strength-fill ${
                        mode === "register" ? registerPasswordStrength.level : resetPasswordStrength.level
                      }`}
                      style={{
                        width: `${
                          mode === "register"
                            ? registerPasswordStrength.progress
                            : resetPasswordStrength.progress
                        }%`,
                      }}
                    />
                  </div>
                  <ul className="password-rules">
                    {(mode === "register"
                      ? registerPasswordStrength.rules
                      : resetPasswordStrength.rules
                    ).map((rule) => (
                      <li key={rule.label} className={rule.met ? "met" : "unmet"}>
                        <span aria-hidden="true">{rule.met ? "OK" : "X"}</span>
                        {rule.label}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {error ? <p className="auth-error">{error}</p> : null}
              {success ? <p className="auth-success-note">{success}</p> : null}

              <button className="nav-item primary-action" type="submit" disabled={busy}>
                {busy
                  ? "Please wait..."
                  : mode === "register"
                    ? "Create Account"
                    : mode === "reset"
                      ? "Reset Password"
                      : "Sign In"}
              </button>
            </form>

            {mode === "signin" ? (
              <>
                <button
                  className="nav-item primary-action"
                  type="button"
                  onClick={() => switchMode("register")}
                  disabled={busy}
                >
                  Need an account? Create one
                </button>
                <button
                  className="nav-item primary-action"
                  type="button"
                  onClick={() => switchMode("reset")}
                  disabled={busy}
                >
                  Forgot password? Use backup code
                </button>
              </>
            ) : (
              <button
                className="nav-item primary-action"
                type="button"
                onClick={() => switchMode("signin")}
                disabled={busy}
              >
                Back to Sign In
              </button>
            )}
          </>
        )}

        <p className="auth-security-note">
          Passwords are bcrypt-hashed, sessions expire after inactivity, and backup codes are shown once.
        </p>
      </article>
    </section>
  );
}

function JobList({
  title,
  jobs,
  emptyText,
}: {
  title: string;
  jobs: DashboardJobItem[];
  emptyText: string;
}) {
  return (
    <article className="panel">
      <h2>{title}</h2>
      {jobs.length === 0 ? (
        <p>{emptyText}</p>
      ) : (
        <ul className="job-list">
          {jobs.map((job) => (
            <li key={job.job_id}>
              <div className="job-primary">
                <strong>{job.project_name}</strong>
                <span>{job.status_display}</span>
              </div>
              <div className="job-secondary">
                <span>{money.format(job.bid_amount || 0)}</span>
                <span>{formatDate(job.scheduled_date)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function DashboardView({ onNavigate, userId }: { onNavigate: (view: NavKey) => void; userId: number }) {
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = async () => {
    try {
      setLoading(true);
      setError(null);
      const payload = await getDashboardSummary();
      setSummary(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSummary();
  }, [userId]);

  if (loading) {
    return <section className="panel"><p>Loading dashboard...</p></section>;
  }

  if (error || !summary) {
    return (
      <section className="panel">
        <h2>Dashboard Error</h2>
        <p>{error ?? "No dashboard data available."}</p>
        <button className="nav-item" onClick={() => void loadSummary()} type="button">
          Retry
        </button>
      </section>
    );
  }

  return (
    <>
      <section className="kpi-grid">
        <article className="panel">
          <h2>Total Revenue</h2>
          <p className="kpi-value">{money.format(summary.metrics.total_revenue)}</p>
        </article>
        <article className="panel">
          <h2>Net Profit</h2>
          <p className="kpi-value">{money.format(summary.metrics.total_profit)}</p>
        </article>
        <article className="panel">
          <h2>Active Jobs</h2>
          <p className="kpi-value">{summary.metrics.active_jobs}</p>
        </article>
        <article className="panel">
          <h2>Profit Margin</h2>
          <p className="kpi-value">{summary.metrics.profit_margin_pct.toFixed(1)}%</p>
        </article>
      </section>

      <section className="panel-grid">
        <JobList
          title="Overdue Jobs"
          jobs={summary.overdue_jobs}
          emptyText="No overdue jobs."
        />
        <JobList
          title="Today's Jobs"
          jobs={summary.todays_jobs}
          emptyText="No jobs scheduled for today."
        />
        <JobList
          title="Upcoming (7 Days)"
          jobs={summary.upcoming_jobs}
          emptyText="No upcoming jobs in the next 7 days."
        />
        <article className="panel">
          <h2>Quick Actions</h2>
          <div className="action-stack">
            <button className="nav-item" onClick={() => onNavigate("bidding")} type="button">
              Create New Bid
            </button>
            <button className="nav-item" onClick={() => onNavigate("jobs")} type="button">
              Open Jobs Board
            </button>
            <button className="nav-item" onClick={() => void loadSummary()} type="button">
              Refresh Dashboard
            </button>
          </div>
        </article>
      </section>

      <section className="panel">
        <h2>Recent Activity</h2>
        <ul className="job-list">
          {summary.recent_jobs.map((job) => (
            <li key={job.job_id}>
              <div className="job-primary">
                <strong>{job.project_name}</strong>
                <span>{job.status_display}</span>
              </div>
              <div className="job-secondary">
                <span>{money.format(job.bid_amount || 0)}</span>
                <span>{formatDate(job.scheduled_date)}</span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

function BiddingView({ userId }: { userId: number }) {
  const [pricingPath, setPricingPath] = useState("");
  const [pricingSheet, setPricingSheet] = useState("");
  const [pdfPath, setPdfPath] = useState("");
  const [pricingFile, setPricingFile] = useState<File | null>(null);
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [projectName, setProjectName] = useState("");
  const [buildingHeight, setBuildingHeight] = useState("");
  const [roofArea, setRoofArea] = useState("");
  const [perimeter, setPerimeter] = useState("");
  const [numCorners, setNumCorners] = useState("4");
  const [preferredMaterial, setPreferredMaterial] = useState("copper");
  const [hasMetalRoof, setHasMetalRoof] = useState(false);
  const [workers, setWorkers] = useState<WorkerInput[]>([{ name: "", wage_per_hour: "", hours: "" }]);
  const [preview, setPreview] = useState<BidPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [isExportingExcel, setIsExportingExcel] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [exportNotice, setExportNotice] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [parseProgress, setParseProgress] = useState(0);
  const [parseStatus, setParseStatus] = useState("");
  const [parseFileLabel, setParseFileLabel] = useState("");
  const [profileLibrary, setProfileLibrary] = useState<BiddingProfileLibrary>(() => readBiddingProfileLibrary(userId));
  const [profileForm, setProfileForm] = useState<BiddingProfileForm>(() => {
    const library = readBiddingProfileLibrary(userId);
    return biddingProfileToFormValues(getActiveBiddingProfile(library).settings);
  });
  const [profileNameInput, setProfileNameInput] = useState<string>(() => {
    const library = readBiddingProfileLibrary(userId);
    return getActiveBiddingProfile(library).name;
  });
  const [customAdjustmentsForm, setCustomAdjustmentsForm] = useState<BiddingCustomPricingAdjustmentForm[]>(() => {
    const library = readBiddingProfileLibrary(userId);
    return settingsToCustomAdjustmentForms(getActiveBiddingProfile(library).settings);
  });
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const pricingPickerRef = useRef<HTMLInputElement | null>(null);
  const pdfPickerRef = useRef<HTMLInputElement | null>(null);
  const parseProgressTimerRef = useRef<number | null>(null);
  const exportNoticeTimerRef = useRef<number | null>(null);

  const stopParseProgressTicker = () => {
    if (parseProgressTimerRef.current !== null) {
      window.clearInterval(parseProgressTimerRef.current);
      parseProgressTimerRef.current = null;
    }
  };

  const startParseProgressTicker = () => {
    stopParseProgressTicker();
    parseProgressTimerRef.current = window.setInterval(() => {
      setParseProgress((prev) => {
        if (prev >= 90) {
          return prev;
        }
        if (prev < 35) {
          return prev + 6;
        }
        if (prev < 70) {
          return prev + 3;
        }
        return prev + 1;
      });
    }, 150);
  };

  const clearExportNoticeTimer = () => {
    if (exportNoticeTimerRef.current !== null) {
      window.clearTimeout(exportNoticeTimerRef.current);
      exportNoticeTimerRef.current = null;
    }
  };

  const showExportNotice = (kind: "success" | "error", message: string) => {
    clearExportNoticeTimer();
    setExportNotice({ kind, message });
    exportNoticeTimerRef.current = window.setTimeout(() => {
      setExportNotice(null);
      exportNoticeTimerRef.current = null;
    }, 5000);
  };

  useEffect(
    () => () => {
      stopParseProgressTicker();
      clearExportNoticeTimer();
    },
    [],
  );
  useEffect(() => {
    const library = readBiddingProfileLibrary(userId);
    const active = getActiveBiddingProfile(library);
    setProfileLibrary(library);
    setProfileForm(biddingProfileToFormValues(active.settings));
    setProfileNameInput(active.name);
    setCustomAdjustmentsForm(settingsToCustomAdjustmentForms(active.settings));
    setProfileMessage(null);
  }, [userId]);

  const updateWorker = (index: number, patch: Partial<WorkerInput>) => {
    setWorkers((prev) =>
      prev.map((worker, i) => (i === index ? { ...worker, ...patch } : worker))
    );
  };

  const setProfileField = (key: BiddingProfileFormField, value: string) => {
    setProfileForm((prev) => ({
      ...prev,
      [key]: value,
    }));
    setError(null);
    setProfileMessage(null);
  };

  const addCustomAdjustmentRow = () => {
    setCustomAdjustmentsForm((prev) => [
      ...prev,
      {
        adjustment_id: createCustomAdjustmentId(),
        name: "",
        mode: "$",
        value: "",
      },
    ]);
    setError(null);
    setProfileMessage(null);
  };

  const updateCustomAdjustment = (
    adjustmentId: string,
    patch: Partial<Pick<BiddingCustomPricingAdjustmentForm, "name" | "mode" | "value">>,
  ) => {
    setCustomAdjustmentsForm((prev) =>
      prev.map((row) =>
        row.adjustment_id === adjustmentId
          ? {
              ...row,
              ...patch,
            }
          : row,
      ),
    );
    setError(null);
    setProfileMessage(null);
  };

  const removeCustomAdjustment = (adjustmentId: string) => {
    setCustomAdjustmentsForm((prev) => prev.filter((row) => row.adjustment_id !== adjustmentId));
    setError(null);
    setProfileMessage(null);
  };

  const updateProfileLibrary = (nextLibrary: BiddingProfileLibrary) => {
    const normalized = normalizeBiddingProfileLibrary(nextLibrary);
    setProfileLibrary(normalized);
    writeBiddingProfileLibrary(userId, normalized);
    return normalized;
  };

  const switchActiveProfile = (profileId: string) => {
    const next = updateProfileLibrary({
      ...profileLibrary,
      active_profile_id: profileId,
    });
    const active = getActiveBiddingProfile(next);
    setProfileForm(biddingProfileToFormValues(active.settings));
    setProfileNameInput(active.name);
    setCustomAdjustmentsForm(settingsToCustomAdjustmentForms(active.settings));
    setError(null);
    setProfileMessage(`Active profile: ${active.name}.`);
  };

  const parseProfileForm = (): BiddingProfileSettings | null => {
    const parseFloatField = (
      key:
        | "labor_markup_pct"
        | "overhead_pct"
        | "profit_pct"
        | "commission_amount"
        | "tools_rental_amount"
        | "shipping_amount"
        | "use_tax_pct"
        | "minimum_bid_amount"
        | "rounding_increment",
      label: string,
      min: number,
      max?: number,
    ): number | null => {
      const raw = profileForm[key];
      const parsed = Number(raw);
      if (!Number.isFinite(parsed)) {
        setError(`${label} must be a valid number.`);
        return null;
      }
      if (parsed < min) {
        setError(`${label} must be at least ${min}.`);
        return null;
      }
      if (typeof max === "number" && parsed > max) {
        setError(`${label} must be at most ${max}.`);
        return null;
      }
      return parsed;
    };

    const laborMarkup = parseFloatField("labor_markup_pct", "Labor markup", 0, 200);
    if (laborMarkup === null) {
      return null;
    }
    const overhead = parseFloatField("overhead_pct", "Overhead", 0, 200);
    if (overhead === null) {
      return null;
    }
    const profit = parseFloatField("profit_pct", "Profit", 0, 300);
    if (profit === null) {
      return null;
    }
    const commission = parseFloatField("commission_amount", "Commission", 0);
    if (commission === null) {
      return null;
    }
    const toolsRental = parseFloatField("tools_rental_amount", "Tools/Rental amount", 0);
    if (toolsRental === null) {
      return null;
    }
    const shipping = parseFloatField("shipping_amount", "Shipping amount", 0);
    if (shipping === null) {
      return null;
    }
    const useTax = parseFloatField("use_tax_pct", "Use tax", 0, 100);
    if (useTax === null) {
      return null;
    }
    const minimumBid = parseFloatField("minimum_bid_amount", "Minimum bid floor", 0);
    if (minimumBid === null) {
      return null;
    }
    const roundingIncrement = parseFloatField("rounding_increment", "Rounding increment", 0);
    if (roundingIncrement === null) {
      return null;
    }

    const toolsRentalType = profileForm.tools_rental_type === "%" ? "%" : "$";
    const roundingMode: BiddingProfileRoundingMode =
      profileForm.rounding_mode === "nearest" || profileForm.rounding_mode === "up" || profileForm.rounding_mode === "down"
        ? profileForm.rounding_mode
        : "none";
    if (roundingMode !== "none" && roundingIncrement <= 0) {
      setError("Rounding increment must be greater than 0 when rounding mode is enabled.");
      return null;
    }
    const normalizedCustomAdjustments: BiddingCustomPricingAdjustment[] = [];
    const seenNames = new Set<string>();
    for (const row of customAdjustmentsForm) {
      const name = row.name.trim();
      const valueRaw = row.value.trim();
      if (!name && !valueRaw) {
        continue;
      }
      if (!name) {
        setError("Each custom pricing box needs a name.");
        return null;
      }
      const parsedValue = Number(valueRaw);
      if (!Number.isFinite(parsedValue) || parsedValue < 0) {
        setError(`Custom pricing "${name}" must have a valid non-negative value.`);
        return null;
      }
      const lowered = name.toLowerCase();
      if (seenNames.has(lowered)) {
        setError(`Custom pricing name "${name}" is duplicated.`);
        return null;
      }
      seenNames.add(lowered);
      normalizedCustomAdjustments.push({
        adjustment_id: row.adjustment_id || createCustomAdjustmentId(),
        name,
        mode: row.mode === "%" ? "%" : "$",
        value: parsedValue,
      });
    }

    return {
      labor_markup_pct: laborMarkup,
      overhead_pct: overhead,
      profit_pct: profit,
      commission_amount: commission,
      tools_rental_amount: toolsRental,
      tools_rental_type: toolsRentalType,
      shipping_amount: shipping,
      use_tax_pct: useTax,
      minimum_bid_amount: minimumBid,
      rounding_increment: roundingIncrement,
      rounding_mode: roundingMode,
      custom_pricing_adjustments: normalizedCustomAdjustments,
    };
  };

  const saveActiveProfileSettings = (settings: BiddingProfileSettings, message?: string) => {
    const active = getActiveBiddingProfile(profileLibrary);
    const now = new Date().toISOString();
    const next = updateProfileLibrary({
      ...profileLibrary,
      profiles: profileLibrary.profiles.map((profile) =>
        profile.profile_id === active.profile_id
          ? { ...profile, settings, updated_at: now }
          : profile,
      ),
    });
    const updatedActive = getActiveBiddingProfile(next);
    setProfileForm(biddingProfileToFormValues(updatedActive.settings));
    setCustomAdjustmentsForm(settingsToCustomAdjustmentForms(updatedActive.settings));
    if (message) {
      setProfileMessage(message);
    }
    return updatedActive;
  };

  const applyProfileDefaults = () => {
    saveActiveProfileSettings(DEFAULT_BIDDING_PROFILE_SETTINGS, "Active profile reset to defaults.");
    setError(null);
  };

  const saveProfile = () => {
    const normalized = parseProfileForm();
    if (!normalized) {
      return;
    }
    saveActiveProfileSettings(normalized, "Active profile saved.");
    setError(null);
  };

  const renameActiveProfile = () => {
    const active = getActiveBiddingProfile(profileLibrary);
    const nextName = normalizeProfileName(profileNameInput);
    const nameTaken = profileLibrary.profiles.some(
      (profile) =>
        profile.profile_id !== active.profile_id &&
        profile.name.trim().toLowerCase() === nextName.toLowerCase(),
    );
    if (nameTaken) {
      setError(`A profile named "${nextName}" already exists.`);
      return;
    }

    const now = new Date().toISOString();
    updateProfileLibrary({
      ...profileLibrary,
      profiles: profileLibrary.profiles.map((profile) =>
        profile.profile_id === active.profile_id
          ? { ...profile, name: nextName, updated_at: now }
          : profile,
      ),
    });
    setProfileNameInput(nextName);
    setError(null);
    setProfileMessage(`Renamed active profile to ${nextName}.`);
  };

  const createProfileFromCurrent = () => {
    const normalized = parseProfileForm();
    if (!normalized) {
      return;
    }
    const nextName = normalizeProfileName(profileNameInput);
    const nameTaken = profileLibrary.profiles.some(
      (profile) => profile.name.trim().toLowerCase() === nextName.toLowerCase(),
    );
    if (nameTaken) {
      setError(`A profile named "${nextName}" already exists.`);
      return;
    }

    const created = buildNamedProfile(nextName, normalized);
    const nextLibrary = updateProfileLibrary({
      active_profile_id: created.profile_id,
      profiles: [...profileLibrary.profiles, created],
    });
    const active = getActiveBiddingProfile(nextLibrary);
    setProfileForm(biddingProfileToFormValues(active.settings));
    setProfileNameInput(active.name);
    setCustomAdjustmentsForm(settingsToCustomAdjustmentForms(active.settings));
    setError(null);
    setProfileMessage(`Created profile ${active.name}.`);
  };

  const deleteActiveProfile = () => {
    if (profileLibrary.profiles.length <= 1) {
      setError("At least one bidding profile is required.");
      return;
    }

    const active = getActiveBiddingProfile(profileLibrary);
    if (!window.confirm(`Delete profile "${active.name}"?`)) {
      return;
    }

    const remaining = profileLibrary.profiles.filter((profile) => profile.profile_id !== active.profile_id);
    const nextLibrary = updateProfileLibrary({
      active_profile_id: remaining[0].profile_id,
      profiles: remaining,
    });
    const nextActive = getActiveBiddingProfile(nextLibrary);
    setProfileForm(biddingProfileToFormValues(nextActive.settings));
    setProfileNameInput(nextActive.name);
    setCustomAdjustmentsForm(settingsToCustomAdjustmentForms(nextActive.settings));
    setError(null);
    setProfileMessage(`Deleted profile ${active.name}. Active profile is now ${nextActive.name}.`);
  };

  const applyParsedPdfFields = (payload: Awaited<ReturnType<typeof parsePdf>>) => {
    const dimensions = payload.extracted.building_dimensions ?? {};
    const info = payload.extracted.project_info ?? {};

    if (typeof info.project_name === "string" && info.project_name.trim()) {
      setProjectName(info.project_name);
    }
    if (typeof dimensions.height === "number") {
      setBuildingHeight(String(dimensions.height));
    }
    if (typeof dimensions.area === "number") {
      setRoofArea(String(dimensions.area));
    }
    if (typeof dimensions.perimeter === "number") {
      setPerimeter(String(dimensions.perimeter));
    }
    if (typeof payload.extracted.num_corners === "number") {
      setNumCorners(String(payload.extracted.num_corners));
    }
  };

  const handleParsePdf = async (fileOverride?: File, knownPath?: string | null) => {
    const activeFile = fileOverride ?? pdfFile;
    const candidatePath = (knownPath ?? pdfPath).trim();
    const activePath = looksLikeFilePath(candidatePath) ? candidatePath : "";
    if (!activeFile && !activePath) {
      setError("Choose a PDF file before parsing.");
      return;
    }

    try {
      setIsParsing(true);
      setError(null);
      setParseProgress(6);
      setParseStatus("Preparing parse...");
      setParseFileLabel(
        activeFile?.name ??
          (activePath ? activePath.split(/[\\/]/).pop() ?? activePath : "Selected PDF"),
      );
      startParseProgressTicker();

      let payload: Awaited<ReturnType<typeof parsePdf>> | null = null;

      if (activePath) {
        setParseStatus("Reading plan data...");
        try {
          payload = await parsePdf({ pdf_file_path: activePath });
        } catch (pathErr) {
          if (!activeFile) {
            throw pathErr;
          }
          setParseStatus("Uploading PDF for parsing...");
          payload = await parsePdfUpload(activeFile);
        }
      } else if (activeFile) {
        setParseStatus("Uploading PDF for parsing...");
        payload = await parsePdfUpload(activeFile);
      }

      if (!payload) {
        throw new Error("PDF parse failed");
      }

      setParseStatus("Applying extracted fields...");
      setParseProgress((prev) => Math.max(prev, 95));
      applyParsedPdfFields(payload);
      setParseStatus("Parse complete");
      setParseProgress(100);
      await new Promise((resolve) => window.setTimeout(resolve, 220));
    } catch (err) {
      setParseStatus("Parse failed");
      setError(err instanceof Error ? err.message : "PDF parse failed");
    } finally {
      stopParseProgressTicker();
      setIsParsing(false);
      window.setTimeout(() => {
        setParseProgress(0);
        setParseStatus("");
      }, 180);
    }
  };

  const handlePricingFileSelected = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const nativePath = getNativeFilePath(file);
    setPricingFile(file);
    setPricingPath(nativePath ?? file.name);
    setError(null);
    event.target.value = "";
  };

  const handlePdfFileSelected = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const nativePath = getNativeFilePath(file);
    setPdfFile(file);
    setPdfPath(nativePath ?? file.name);
    setError(null);
    event.target.value = "";
    void handleParsePdf(file, nativePath);
  };

  const buildWorkersPayload = () =>
    workers
      .filter((worker) => worker.name.trim().length > 0)
      .map((worker) => ({
        name: worker.name.trim(),
        wage_per_hour: toNumber(worker.wage_per_hour) ?? 0,
        hours: toNumber(worker.hours) ?? 0,
      }));

  const buildSharedBidPayload = (profilePayload: BiddingProfileSettings) => ({
    pricing_sheet: pricingSheet.trim() || undefined,
    compliance_code: "DUAL",
    project_data: {
      project_name: projectName.trim() || "Lightning Protection Bid",
      building_height_ft: toNumber(buildingHeight) ?? 0,
      roof_area_sqft: toNumber(roofArea) ?? 0,
      perimeter_ft: toNumber(perimeter),
      num_corners: Math.max(1, Math.round(toNumber(numCorners) ?? 4)),
      preferred_material: preferredMaterial,
      has_metal_roof: hasMetalRoof,
      labor_markup_pct: profilePayload.labor_markup_pct,
      overhead_pct: profilePayload.overhead_pct,
      profit_pct: profilePayload.profit_pct,
      commission_amount: profilePayload.commission_amount,
      tools_rental_amount: profilePayload.tools_rental_amount,
      tools_rental_type: profilePayload.tools_rental_type,
      shipping_amount: profilePayload.shipping_amount,
      use_tax_pct: profilePayload.use_tax_pct,
      minimum_bid_amount: profilePayload.minimum_bid_amount,
      rounding_increment: profilePayload.rounding_increment,
      rounding_mode: profilePayload.rounding_mode,
      custom_pricing_adjustments: profilePayload.custom_pricing_adjustments.map((item) => ({
        name: item.name,
        mode: item.mode,
        value: item.value,
      })),
    },
    workers: buildWorkersPayload(),
  });

  const buildExportFileName = (extension: "xlsx" | "pdf"): string => {
    const candidate = preview?.project_name || projectName.trim() || "Lightning Protection Bid";
    const safeName = sanitizeFileName(candidate).replace(/_+/g, "_");
    const datePart = new Date().toISOString().slice(0, 10);
    return `${safeName || "Lightning_Protection_Bid"}_${datePart}.${extension}`;
  };

  const handlePreview = async (event: FormEvent) => {
    event.preventDefault();
    const trimmedPricingPath = pricingPath.trim();
    if (!pricingFile && !trimmedPricingPath) {
      setError("Choose a pricing Excel file before previewing.");
      return;
    }
    const profilePayload = parseProfileForm();
    if (!profilePayload) {
      return;
    }

    setIsBusy(true);
    setError(null);
    setExportNotice(null);
    saveActiveProfileSettings(profilePayload);

    try {
      const sharedPayload = buildSharedBidPayload(profilePayload);

      const payload = pricingFile
        ? await previewBidUpload(pricingFile, sharedPayload)
        : await previewBid({
            pricing_file_path: trimmedPricingPath,
            ...sharedPayload,
          });
      setPreview(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setIsBusy(false);
    }
  };

  const handleExportExcel = async () => {
    const trimmedPricingPath = pricingPath.trim();
    if (!pricingFile && !trimmedPricingPath) {
      setError("Choose a pricing Excel file before exporting.");
      return;
    }

    const profilePayload = parseProfileForm();
    if (!profilePayload) {
      return;
    }

    setIsExportingExcel(true);
    setError(null);
    setExportNotice(null);
    saveActiveProfileSettings(profilePayload);

    try {
      const sharedPayload = buildSharedBidPayload(profilePayload);
      const filename = buildExportFileName("xlsx");
      const blob = pricingFile
        ? await exportBidExcelUpload(pricingFile, sharedPayload)
        : await exportBidExcel({
            pricing_file_path: trimmedPricingPath,
            ...sharedPayload,
          });
      downloadBlob(filename, blob);
      showExportNotice("success", `Excel exported: ${filename}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Excel export failed");
      showExportNotice("error", err instanceof Error ? err.message : "Excel export failed");
    } finally {
      setIsExportingExcel(false);
    }
  };

  const handleExportPdf = async () => {
    const trimmedPricingPath = pricingPath.trim();
    if (!pricingFile && !trimmedPricingPath) {
      setError("Choose a pricing Excel file before exporting.");
      return;
    }

    const profilePayload = parseProfileForm();
    if (!profilePayload) {
      return;
    }

    setIsExportingPdf(true);
    setError(null);
    setExportNotice(null);
    saveActiveProfileSettings(profilePayload);

    try {
      const sharedPayload = buildSharedBidPayload(profilePayload);
      const filename = buildExportFileName("pdf");
      const blob = pricingFile
        ? await exportBidPdfUpload(pricingFile, sharedPayload)
        : await exportBidPdf({
            pricing_file_path: trimmedPricingPath,
            ...sharedPayload,
          });
      downloadBlob(filename, blob);
      showExportNotice("success", `PDF exported: ${filename}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF export failed");
      showExportNotice("error", err instanceof Error ? err.message : "PDF export failed");
    } finally {
      setIsExportingPdf(false);
    }
  };

  return (
    <section className="panel-stack">
      <article className="panel">
        <h2>Bidding Workspace</h2>
        <form className="form-grid" onSubmit={handlePreview}>
          <div className="full-width file-picker-stack">
            <h3>Source Files</h3>
            <div className="file-picker-row">
              <label>Pricing Excel File</label>
              <div className="file-picker-controls">
                <input
                  value={pricingPath}
                  onChange={(e) => setPricingPath(e.target.value)}
                  placeholder="Select an Excel pricing file"
                  required={!pricingFile}
                />
                <button
                  className="nav-item compact"
                  type="button"
                  onClick={() => pricingPickerRef.current?.click()}
                >
                  Choose Excel
                </button>
              </div>
            </div>

            <div className="file-picker-row">
              <label>Plan PDF File</label>
              <div className="file-picker-controls">
                <input
                  value={pdfPath}
                  onChange={(e) => setPdfPath(e.target.value)}
                  placeholder="Select a PDF plan file"
                />
                <button
                  className="nav-item compact"
                  type="button"
                  onClick={() => pdfPickerRef.current?.click()}
                  disabled={isParsing}
                >
                  {isParsing ? "Parsing..." : "Choose PDF"}
                </button>
                <button
                  className="nav-item compact"
                  type="button"
                  onClick={() => void handleParsePdf()}
                  disabled={isParsing || (!pdfFile && !pdfPath.trim())}
                >
                  Re-Parse
                </button>
              </div>
            </div>

            <input
              ref={pricingPickerRef}
              type="file"
              accept=".xlsx,.xls,.xlsm,.csv"
              onChange={handlePricingFileSelected}
              style={{ display: "none" }}
            />
            <input
              ref={pdfPickerRef}
              type="file"
              accept=".pdf"
              onChange={handlePdfFileSelected}
              style={{ display: "none" }}
            />

            <p className="file-picker-hint">PDF is parsed automatically when selected.</p>
            {isParsing ? (
              <div className="parse-loading-box" role="status" aria-live="polite">
                <div className="parse-loading-head">
                  <strong>Parsing PDF</strong>
                  <span>{Math.round(parseProgress)}%</span>
                </div>
                <p className="parse-loading-file" title={parseFileLabel}>
                  {parseFileLabel || "Selected plan PDF"}
                </p>
                <div className="parse-loading-track">
                  <div className="parse-loading-fill" style={{ width: `${parseProgress}%` }} />
                </div>
                <p className="parse-loading-status">
                  {parseStatus || "Extracting project fields from plan..."}
                </p>
              </div>
            ) : null}
          </div>

          <label>
            Sheet Name
            <input value={pricingSheet} onChange={(e) => setPricingSheet(e.target.value)} />
          </label>
          <label className="full-width">
            Project Name
            <input value={projectName} onChange={(e) => setProjectName(e.target.value)} />
          </label>
          <label>
            Building Height (ft)
            <input value={buildingHeight} onChange={(e) => setBuildingHeight(e.target.value)} />
          </label>
          <label>
            Roof Area (sqft)
            <input value={roofArea} onChange={(e) => setRoofArea(e.target.value)} />
          </label>
          <label>
            Perimeter (ft)
            <input value={perimeter} onChange={(e) => setPerimeter(e.target.value)} />
          </label>
          <label>
            Corners
            <input value={numCorners} onChange={(e) => setNumCorners(e.target.value)} />
          </label>
          <label>
            Preferred Material
            <select
              value={preferredMaterial}
              onChange={(e) => setPreferredMaterial(e.target.value)}
            >
              <option value="copper">Copper</option>
              <option value="aluminum">Aluminum</option>
            </select>
          </label>
          <label className="checkbox">
            <input
              checked={hasMetalRoof}
              onChange={(e) => setHasMetalRoof(e.target.checked)}
              type="checkbox"
            />
            Metal roof
          </label>

          <div className="full-width bidding-profile-panel">
            <div className="bidding-profile-header">
              <h3>Bidding Profile</h3>
              <div className="bidding-profile-actions">
                <button className="nav-item compact" type="button" onClick={saveProfile}>
                  Save Active
                </button>
                <button className="nav-item compact" type="button" onClick={applyProfileDefaults}>
                  Reset Active
                </button>
                <button className="nav-item compact" type="button" onClick={createProfileFromCurrent}>
                  Save As New
                </button>
                <button className="nav-item compact" type="button" onClick={deleteActiveProfile}>
                  Delete Active
                </button>
              </div>
            </div>
            <p className="bidding-profile-note">
              Company-level pricing settings used for this preview. Profiles are saved per user.
            </p>
            {profileMessage ? <p className="bidding-profile-feedback">{profileMessage}</p> : null}
            <div className="bidding-profile-meta">
              <label>
                Active Profile
                <select
                  value={profileLibrary.active_profile_id}
                  onChange={(e) => switchActiveProfile(e.target.value)}
                >
                  {profileLibrary.profiles.map((profile) => (
                    <option key={profile.profile_id} value={profile.profile_id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Profile Name
                <input
                  value={profileNameInput}
                  onChange={(e) => {
                    setProfileNameInput(e.target.value);
                    setProfileMessage(null);
                  }}
                  placeholder="Commercial"
                />
              </label>
              <div className="bidding-profile-name-actions">
                <button className="nav-item compact" type="button" onClick={renameActiveProfile}>
                  Rename Active
                </button>
              </div>
            </div>
            <div className="bidding-profile-grid">
              <label>
                Labor Markup (%)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={profileForm.labor_markup_pct}
                  onChange={(e) => setProfileField("labor_markup_pct", e.target.value)}
                />
              </label>
              <label>
                Overhead (%)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={profileForm.overhead_pct}
                  onChange={(e) => setProfileField("overhead_pct", e.target.value)}
                />
              </label>
              <label>
                Profit (%)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={profileForm.profit_pct}
                  onChange={(e) => setProfileField("profit_pct", e.target.value)}
                />
              </label>
              <label>
                Use Tax (%)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={profileForm.use_tax_pct}
                  onChange={(e) => setProfileField("use_tax_pct", e.target.value)}
                />
              </label>
              <label>
                Shipping ($)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={profileForm.shipping_amount}
                  onChange={(e) => setProfileField("shipping_amount", e.target.value)}
                />
              </label>
              <label>
                Commission ($)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={profileForm.commission_amount}
                  onChange={(e) => setProfileField("commission_amount", e.target.value)}
                />
              </label>
              <label>
                Tools/Rental Type
                <select
                  value={profileForm.tools_rental_type}
                  onChange={(e) => setProfileField("tools_rental_type", e.target.value)}
                >
                  <option value="$">Flat Dollar ($)</option>
                  <option value="%">Percent of Subtotal (%)</option>
                </select>
              </label>
              <label>
                Tools/Rental Value
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={profileForm.tools_rental_amount}
                  onChange={(e) => setProfileField("tools_rental_amount", e.target.value)}
                />
              </label>
              <label>
                Minimum Bid Floor ($)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={profileForm.minimum_bid_amount}
                  onChange={(e) => setProfileField("minimum_bid_amount", e.target.value)}
                />
              </label>
              <label>
                Rounding Mode
                <select
                  value={profileForm.rounding_mode}
                  onChange={(e) => setProfileField("rounding_mode", e.target.value)}
                >
                  <option value="none">None</option>
                  <option value="nearest">Nearest Increment</option>
                  <option value="up">Always Up</option>
                  <option value="down">Always Down</option>
                </select>
              </label>
              <label>
                Rounding Increment ($)
                <input
                  type="number"
                  step="1"
                  min="0"
                  value={profileForm.rounding_increment}
                  onChange={(e) => setProfileField("rounding_increment", e.target.value)}
                />
              </label>
            </div>
            <div className="custom-pricing-panel">
              <div className="custom-pricing-header">
                <h4>Custom Pricing Boxes</h4>
                <button className="nav-item compact" type="button" onClick={addCustomAdjustmentRow}>
                  Add Pricing Box
                </button>
              </div>
              <p className="custom-pricing-note">
                Add your own line items. `%` uses subtotal as the base.
              </p>
              {customAdjustmentsForm.length === 0 ? (
                <p className="custom-pricing-empty">No custom pricing boxes yet.</p>
              ) : (
                <div className="custom-pricing-list">
                  {customAdjustmentsForm.map((item) => (
                    <div key={item.adjustment_id} className="custom-pricing-row">
                      <input
                        placeholder="Line item name"
                        value={item.name}
                        onChange={(e) =>
                          updateCustomAdjustment(item.adjustment_id, { name: e.target.value })
                        }
                      />
                      <select
                        value={item.mode}
                        onChange={(e) =>
                          updateCustomAdjustment(item.adjustment_id, { mode: e.target.value === "%" ? "%" : "$" })
                        }
                      >
                        <option value="$">$</option>
                        <option value="%">%</option>
                      </select>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        placeholder="Value"
                        value={item.value}
                        onChange={(e) =>
                          updateCustomAdjustment(item.adjustment_id, { value: e.target.value })
                        }
                      />
                      <button
                        className="nav-item compact"
                        type="button"
                        onClick={() => removeCustomAdjustment(item.adjustment_id)}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="full-width">
            <h3>Workers</h3>
            <div className="worker-grid">
              {workers.map((worker, index) => (
                <div key={index} className="worker-row">
                  <input
                    placeholder="Name"
                    value={worker.name}
                    onChange={(e) => updateWorker(index, { name: e.target.value })}
                  />
                  <input
                    placeholder="Wage/hour"
                    value={worker.wage_per_hour}
                    onChange={(e) => updateWorker(index, { wage_per_hour: e.target.value })}
                  />
                  <input
                    placeholder="Hours"
                    value={worker.hours}
                    onChange={(e) => updateWorker(index, { hours: e.target.value })}
                  />
                </div>
              ))}
            </div>
            <button
              className="nav-item compact"
              onClick={() => setWorkers((prev) => [...prev, { name: "", wage_per_hour: "", hours: "" }])}
              type="button"
            >
              Add Worker
            </button>
          </div>

          <div className="full-width action-row">
            <button className="nav-item" type="submit" disabled={isBusy}>
              {isBusy ? "Calculating..." : "Preview Bid"}
            </button>
          </div>
        </form>
      </article>

      {error ? <article className="panel error-panel"><p>{error}</p></article> : null}

      {preview ? (
        <article className="panel">
          <h2>Bid Preview Result</h2>
          <div className="preview-grid">
            <div>Project: {preview.project_name}</div>
            <div>Subtotal: {money.format(preview.subtotal)}</div>
            <div>Total With Markup: {money.format(preview.total_with_markup)}</div>
            <div>Final Bid: {money.format(preview.final_bid_amount)}</div>
            <div>Materials: {money.format(preview.material_total)}</div>
            <div>Labor: {money.format(preview.labor_total)}</div>
          </div>
          <details className="calc-explain-panel" open>
            <summary>Explain Calculation</summary>
            <div className="calc-explain-body">
              <div className="calc-explain-totals">
                <p>Before Floor/Rounding: {money.format(preview.calculation_breakdown.totals.final_before_floor_rounding)}</p>
                <p>Minimum Floor Adj: {money.format(preview.calculation_breakdown.totals.minimum_floor_adjustment)}</p>
                <p>Rounding Adj: {money.format(preview.calculation_breakdown.totals.rounding_adjustment)}</p>
                <p><strong>Final Bid: {money.format(preview.calculation_breakdown.totals.final_bid_amount)}</strong></p>
              </div>

              <ul className="calc-line-list">
                {preview.calculation_breakdown.line_items.map((item) => (
                  <li key={item.key}>
                    <span>{item.label}</span>
                    <strong>{money.format(item.amount)}</strong>
                  </li>
                ))}
              </ul>

              {preview.calculation_breakdown.custom_adjustments.length > 0 ? (
                <div className="calc-custom-list">
                  <h4>Custom Pricing Boxes Applied</h4>
                  <ul>
                    {preview.calculation_breakdown.custom_adjustments.map((item, index) => (
                      <li key={`${item.name}-${index}`}>
                        <span>
                          {item.name} ({item.mode === "%" ? `${item.value}% of subtotal` : money.format(item.value)})
                        </span>
                        <strong>{money.format(item.applied_amount)}</strong>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <details className="calc-inputs-panel">
                <summary>Profile Inputs Used</summary>
                <div className="calc-inputs-grid">
                  <div>Labor markup: {preview.calculation_breakdown.inputs.labor_markup_pct}%</div>
                  <div>Overhead: {preview.calculation_breakdown.inputs.overhead_pct}%</div>
                  <div>Profit: {preview.calculation_breakdown.inputs.profit_pct}%</div>
                  <div>Use tax: {preview.calculation_breakdown.inputs.use_tax_pct}%</div>
                  <div>Tools/rental: {preview.calculation_breakdown.inputs.tools_rental_amount}{preview.calculation_breakdown.inputs.tools_rental_type}</div>
                  <div>Minimum bid: {money.format(preview.calculation_breakdown.inputs.minimum_bid_amount)}</div>
                  <div>Rounding mode: {preview.calculation_breakdown.inputs.rounding_mode}</div>
                  <div>Rounding increment: {money.format(preview.calculation_breakdown.inputs.rounding_increment)}</div>
                </div>
              </details>
            </div>
          </details>
          <h3>Sections</h3>
          <ul className="job-list">
            {preview.sections.map((section) => (
              <li key={section.name}>
                <div className="job-primary">
                  <strong>{section.name}</strong>
                  <span>{section.items} items</span>
                </div>
                <div className="job-secondary">
                  <span>{money.format(section.material_total)}</span>
                  <span>{money.format(section.section_total)}</span>
                </div>
              </li>
            ))}
          </ul>
          {exportNotice ? (
            <p
              className={`export-notice ${exportNotice.kind}`}
              role={exportNotice.kind === "error" ? "alert" : "status"}
              aria-live="polite"
            >
              {exportNotice.message}
            </p>
          ) : null}
          <div className="action-row export-actions">
            <button
              className="nav-item"
              type="button"
              onClick={() => void handleExportExcel()}
              disabled={isBusy || isExportingExcel || isExportingPdf}
            >
              {isExportingExcel ? "Exporting Excel..." : "Export Excel"}
            </button>
            <button
              className="nav-item"
              type="button"
              onClick={() => void handleExportPdf()}
              disabled={isBusy || isExportingExcel || isExportingPdf}
            >
              {isExportingPdf ? "Exporting PDF..." : "Export PDF"}
            </button>
          </div>
        </article>
      ) : null}
    </section>
  );
}

function JobsView({ userId, username }: { userId: number; username: string }) {
  const [board, setBoard] = useState<JobsBoardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatingJobId, setUpdatingJobId] = useState<number | null>(null);
  const [workflowInputs, setWorkflowInputs] = useState<
    Record<
      number,
      {
        scheduled_date: string;
        start_date: string;
        completion_date: string;
        invoice_date: string;
        invoice_number: string;
        assigned_crew: string;
        note: string;
      }
    >
  >({});
  const [alertSettings, setAlertSettings] = useState<WorkflowAlertSettings>(() => readWorkflowAlertSettings(userId));
  const [alertForm, setAlertForm] = useState<WorkflowAlertSettingsForm>(() =>
    alertSettingsToFormValues(readWorkflowAlertSettings(userId)),
  );
  const [isAlertsDialogOpen, setIsAlertsDialogOpen] = useState(false);
  const [isAlertsUnlocked, setIsAlertsUnlocked] = useState(false);
  const [alertsPassword, setAlertsPassword] = useState("");
  const [alertsBusy, setAlertsBusy] = useState(false);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  const getWorkflowInput = (jobId: number) =>
    workflowInputs[jobId] ?? {
      scheduled_date: "",
      start_date: "",
      completion_date: "",
      invoice_date: "",
      invoice_number: "",
      assigned_crew: "",
      note: "",
    };

  const setWorkflowInput = (
    jobId: number,
    key:
      | "scheduled_date"
      | "start_date"
      | "completion_date"
      | "invoice_date"
      | "invoice_number"
      | "assigned_crew"
      | "note",
    value: string,
  ) => {
    setWorkflowInputs((prev) => ({
      ...prev,
      [jobId]: {
        ...getWorkflowInput(jobId),
        [key]: value,
      },
    }));
  };

  const clearWorkflowInput = (jobId: number) => {
    setWorkflowInputs((prev) => {
      const next = { ...prev };
      delete next[jobId];
      return next;
    });
  };

  useEffect(() => {
    const next = readWorkflowAlertSettings(userId);
    setAlertSettings(next);
    setAlertForm(alertSettingsToFormValues(next));
  }, [userId]);

  const isIsoDate = (value: string): boolean => /^\d{4}-\d{2}-\d{2}$/.test(value.trim());
  const parseCrewCsv = (value: string): string[] =>
    value
      .split(",")
      .map((member) => member.trim())
      .filter((member) => member.length > 0);

  const loadBoard = async (refreshOnly: boolean) => {
    try {
      if (refreshOnly) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      const payload = await getJobsBoard();
      setBoard(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs board");
    } finally {
      if (refreshOnly) {
        setRefreshing(false);
      } else {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void loadBoard(false);
  }, [userId]);

  const handleStatusAdvance = async (job: DashboardJobItem, nextStatus: JobBoardStatus) => {
    const input = getWorkflowInput(job.job_id);
    const note = input.note.trim();
    const crews = parseCrewCsv(input.assigned_crew);
    const payload: {
      new_status: JobBoardStatus;
      note?: string;
      start_date?: string;
      completion_date?: string;
      invoice_date?: string;
      invoice_number?: string;
      assigned_crew?: string[];
    } = {
      new_status: nextStatus,
    };

    if (nextStatus === "in_progress") {
      if (!isIsoDate(input.start_date)) {
        setError("Enter a valid start date in YYYY-MM-DD format.");
        return;
      }
      if (crews.length === 0) {
        setError("Enter assigned crew (comma-separated) before moving to In Progress.");
        return;
      }
      if (!note) {
        setError("Add a transition note before moving to In Progress.");
        return;
      }
      payload.start_date = input.start_date.trim();
      payload.assigned_crew = crews;
      payload.note = note;
    } else if (nextStatus === "inspection") {
      if (!note) {
        setError("Add a transition note before moving to Inspection.");
        return;
      }
      payload.note = note;
    } else if (nextStatus === "completed") {
      if (!isIsoDate(input.completion_date)) {
        setError("Enter a valid completion date in YYYY-MM-DD format.");
        return;
      }
      if (!note) {
        setError("Add a transition note before marking Completed.");
        return;
      }
      payload.completion_date = input.completion_date.trim();
      payload.note = note;
    } else if (nextStatus === "invoiced") {
      if (!isIsoDate(input.invoice_date)) {
        setError("Enter a valid invoice date in YYYY-MM-DD format.");
        return;
      }
      if (!input.invoice_number.trim()) {
        setError("Invoice number is required before marking Invoiced.");
        return;
      }
      if (!note) {
        setError("Add a transition note before marking Invoiced.");
        return;
      }
      payload.invoice_date = input.invoice_date.trim();
      payload.invoice_number = input.invoice_number.trim();
      payload.note = note;
    }

    try {
      setUpdatingJobId(job.job_id);
      setError(null);
      await updateJobStatus(job.job_id, payload);
      clearWorkflowInput(job.job_id);
      await loadBoard(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update job status");
    } finally {
      setUpdatingJobId(null);
    }
  };

  const openAlertsDialog = () => {
    setAlertsError(null);
    setAlertsPassword("");
    setIsAlertsUnlocked(false);
    setAlertForm(alertSettingsToFormValues(alertSettings));
    setIsAlertsDialogOpen(true);
  };

  const closeAlertsDialog = () => {
    setIsAlertsDialogOpen(false);
    setIsAlertsUnlocked(false);
    setAlertsPassword("");
    setAlertsError(null);
    setAlertsBusy(false);
  };

  const setAlertFieldValue = (key: WorkflowAlertSettingsField, value: string) => {
    setAlertForm((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const unlockAlertsSettings = async (event: FormEvent) => {
    event.preventDefault();

    if (!alertsPassword.trim()) {
      setAlertsError("Enter your password to access Alerts settings.");
      return;
    }

    try {
      setAlertsBusy(true);
      setAlertsError(null);
      const verifyResult = await verifyPassword({
        password: alertsPassword,
      });
      if (!verifyResult.valid) {
        setAlertsError("Password confirmation failed for this account.");
        return;
      }
      setIsAlertsUnlocked(true);
      setAlertsPassword("");
      setAlertForm(alertSettingsToFormValues(alertSettings));
    } catch (err) {
      setAlertsError(err instanceof Error ? err.message : "Password confirmation failed.");
    } finally {
      setAlertsBusy(false);
    }
  };

  const saveAlertSettings = (event: FormEvent) => {
    event.preventDefault();

    const nextSettings = { ...alertSettings };
    for (const field of workflowAlertSettingFields) {
      const rawValue = (alertForm[field.key] ?? "").trim();
      if (!rawValue) {
        setAlertsError(`${field.label} is required.`);
        return;
      }
      const parsed = Number(rawValue);
      if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
        setAlertsError(`${field.label} must be a whole number.`);
        return;
      }
      if (parsed < field.min || parsed > field.max) {
        setAlertsError(`${field.label} must be between ${field.min} and ${field.max} days.`);
        return;
      }
      nextSettings[field.key] = parsed;
    }

    setAlertSettings(nextSettings);
    writeWorkflowAlertSettings(userId, nextSettings);
    closeAlertsDialog();
  };

  const handleApproveAndSchedule = async (job: DashboardJobItem) => {
    const input = getWorkflowInput(job.job_id);
    const scheduledDate = input.scheduled_date.trim();
    const crews = parseCrewCsv(input.assigned_crew);
    const note = input.note.trim();

    if (!isIsoDate(scheduledDate)) {
      setError("Enter a valid scheduled date in YYYY-MM-DD format before approving.");
      return;
    }
    if (crews.length === 0) {
      setError("Enter assigned crew (comma-separated) before approving.");
      return;
    }
    if (!note) {
      setError("Add an approval note before scheduling.");
      return;
    }

    try {
      setUpdatingJobId(job.job_id);
      setError(null);
      await approveJob(job.job_id, {
        scheduled_date: scheduledDate,
        assigned_crew: crews,
        note,
      });
      clearWorkflowInput(job.job_id);
      await loadBoard(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve and schedule job");
    } finally {
      setUpdatingJobId(null);
    }
  };

  if (loading) {
    return <section className="panel"><p>Loading jobs board...</p></section>;
  }

  if (!board) {
    return (
      <section className="panel">
        <h2>Jobs Board Error</h2>
        <p>{error ?? "No jobs board data available."}</p>
        <button className="nav-item" onClick={() => void loadBoard(false)} type="button">
          Retry
        </button>
      </section>
    );
  }

  return (
    <section className="panel-stack jobs-board-shell">
      <article className="panel jobs-board-header">
        <div>
          <h2>Jobs Board</h2>
          <p>
            Track and advance jobs through approval, execution, completion, and invoicing with required
            transition fields.
          </p>
        </div>
        <div className="jobs-header-actions">
          <button
            className="nav-item"
            onClick={openAlertsDialog}
            type="button"
            disabled={updatingJobId !== null}
          >
            ⚙ Alerts
          </button>
          <button
            className="nav-item"
            onClick={() => void loadBoard(true)}
            type="button"
            disabled={refreshing || updatingJobId !== null}
          >
            {refreshing ? "Refreshing..." : "Refresh Board"}
          </button>
        </div>
      </article>

      {error ? <article className="panel error-panel"><p>{error}</p></article> : null}

      <section className="jobs-board-grid">
        {jobsBoardColumns.map((column) => {
          const jobs = board[column.key];
          const nextStatus = column.nextStatus;
          return (
            <article key={column.key} className={`panel jobs-column status-${column.key}`}>
              <header className="jobs-column-header">
                <h3>{column.label}</h3>
                <span className="jobs-count">{jobs.length}</span>
              </header>

              <div className="jobs-column-list">
                {jobs.length === 0 ? (
                  <p className="jobs-empty">{column.emptyText}</p>
                ) : (
                  jobs.map((job) => {
                    const input = getWorkflowInput(job.job_id);
                    const workflowAlert = evaluateWorkflowAlert(job, alertSettings);
                    return (
                      <article
                        key={job.job_id}
                        className={`job-board-card${workflowAlertLevelClass(workflowAlert)}`}
                      >
                        <div className="job-primary">
                          <strong>{job.project_name}</strong>
                          <div className="job-status-row">
                            <span className="job-status-chip">{job.status_display}</span>
                            {workflowAlert !== "none" ? (
                              <span className={`job-alert-chip ${workflowAlert}`}>
                                {workflowAlertLabel(workflowAlert)}
                              </span>
                            ) : null}
                          </div>
                        </div>
                        <div className="job-secondary">
                          <span>{money.format(job.bid_amount || 0)}</span>
                          <span>{formatDate(job.scheduled_date)}</span>
                        </div>

                        {job.assigned_crew && job.assigned_crew.length > 0 ? (
                          <p className="calendar-job-crew">Crew: {job.assigned_crew.join(", ")}</p>
                        ) : null}
                        {job.invoice_number ? (
                          <p className="calendar-job-crew">
                            Invoice: {job.invoice_number} ({formatDate(job.invoice_date)})
                          </p>
                        ) : null}

                        {column.actionType === "approve" && column.actionLabel ? (
                          <div className="jobs-approve-row">
                            <input
                              className="jobs-date-input"
                              placeholder="Scheduled date (YYYY-MM-DD)"
                              value={input.scheduled_date}
                              onChange={(e) => setWorkflowInput(job.job_id, "scheduled_date", e.target.value)}
                              disabled={updatingJobId === job.job_id}
                            />
                            <input
                              className="jobs-date-input"
                              placeholder="Assigned crew (comma-separated)"
                              value={input.assigned_crew}
                              onChange={(e) => setWorkflowInput(job.job_id, "assigned_crew", e.target.value)}
                              disabled={updatingJobId === job.job_id}
                            />
                            <textarea
                              className="jobs-note-input"
                              placeholder="Approval note"
                              value={input.note}
                              onChange={(e) => setWorkflowInput(job.job_id, "note", e.target.value)}
                              disabled={updatingJobId === job.job_id}
                            />
                            <button
                              className="nav-item compact jobs-advance-btn"
                              onClick={() => void handleApproveAndSchedule(job)}
                              type="button"
                              disabled={updatingJobId === job.job_id}
                            >
                              {updatingJobId === job.job_id ? "Updating..." : column.actionLabel}
                            </button>
                          </div>
                        ) : null}

                        {column.actionType === "advance" && nextStatus && column.actionLabel ? (
                          <div className="jobs-approve-row">
                            {nextStatus === "in_progress" ? (
                              <>
                                <input
                                  className="jobs-date-input"
                                  placeholder="Start date (YYYY-MM-DD)"
                                  value={input.start_date}
                                  onChange={(e) => setWorkflowInput(job.job_id, "start_date", e.target.value)}
                                  disabled={updatingJobId === job.job_id}
                                />
                                <input
                                  className="jobs-date-input"
                                  placeholder="Assigned crew (comma-separated)"
                                  value={input.assigned_crew}
                                  onChange={(e) => setWorkflowInput(job.job_id, "assigned_crew", e.target.value)}
                                  disabled={updatingJobId === job.job_id}
                                />
                              </>
                            ) : null}

                            {nextStatus === "completed" ? (
                              <input
                                className="jobs-date-input"
                                placeholder="Completion date (YYYY-MM-DD)"
                                value={input.completion_date}
                                onChange={(e) => setWorkflowInput(job.job_id, "completion_date", e.target.value)}
                                disabled={updatingJobId === job.job_id}
                              />
                            ) : null}

                            {nextStatus === "invoiced" ? (
                              <>
                                <input
                                  className="jobs-date-input"
                                  placeholder="Invoice date (YYYY-MM-DD)"
                                  value={input.invoice_date}
                                  onChange={(e) => setWorkflowInput(job.job_id, "invoice_date", e.target.value)}
                                  disabled={updatingJobId === job.job_id}
                                />
                                <input
                                  className="jobs-date-input"
                                  placeholder="Invoice number"
                                  value={input.invoice_number}
                                  onChange={(e) => setWorkflowInput(job.job_id, "invoice_number", e.target.value)}
                                  disabled={updatingJobId === job.job_id}
                                />
                              </>
                            ) : null}

                            <textarea
                              className="jobs-note-input"
                              placeholder="Transition note"
                              value={input.note}
                              onChange={(e) => setWorkflowInput(job.job_id, "note", e.target.value)}
                              disabled={updatingJobId === job.job_id}
                            />
                            <button
                              className="nav-item compact jobs-advance-btn"
                              onClick={() => void handleStatusAdvance(job, nextStatus)}
                              type="button"
                              disabled={updatingJobId === job.job_id}
                            >
                              {updatingJobId === job.job_id ? "Updating..." : column.actionLabel}
                            </button>
                          </div>
                        ) : null}

                        {!column.actionType ? (
                          <p className="jobs-complete-label">Workflow complete</p>
                        ) : null}
                      </article>
                    );
                  })
                )}
              </div>
            </article>
          );
        })}
      </section>

      {isAlertsDialogOpen ? (
        <div className="alerts-modal-backdrop" role="presentation">
          <article className="panel alerts-modal" role="dialog" aria-modal="true" aria-labelledby="alerts-modal-title">
            <header className="alerts-modal-header">
              <h3 id="alerts-modal-title">Workflow Alerts</h3>
              <button
                className="nav-item compact"
                type="button"
                onClick={closeAlertsDialog}
                disabled={alertsBusy}
              >
                Close
              </button>
            </header>
            <p className="alerts-modal-intro">
              Configure warning and overdue timelines for workflow steps. Password confirmation is required.
            </p>
            {alertsError ? <p className="alerts-modal-error">{alertsError}</p> : null}

            {!isAlertsUnlocked ? (
              <form className="alerts-lock-form" onSubmit={unlockAlertsSettings}>
                <label>
                  Account Password
                  <input
                    type="password"
                    value={alertsPassword}
                    onChange={(e) => setAlertsPassword(e.target.value)}
                    autoComplete="current-password"
                    required
                    disabled={alertsBusy}
                  />
                </label>
                <button className="nav-item" type="submit" disabled={alertsBusy}>
                  {alertsBusy ? "Checking..." : "Unlock Alerts Settings"}
                </button>
              </form>
            ) : (
              <form className="alerts-settings-form" onSubmit={saveAlertSettings}>
                {workflowAlertSettingFields.map((field) => (
                  <label key={field.key}>
                    {field.label}
                    <input
                      type="number"
                      min={field.min}
                      max={field.max}
                      step={1}
                      value={alertForm[field.key]}
                      onChange={(e) => setAlertFieldValue(field.key, e.target.value)}
                    />
                    <small>{field.description}</small>
                  </label>
                ))}
                <div className="alerts-modal-actions">
                  <button
                    className="nav-item compact"
                    type="button"
                    onClick={() => setAlertForm(alertSettingsToFormValues(alertSettings))}
                  >
                    Reset
                  </button>
                  <button className="nav-item" type="submit">Save Alerts</button>
                </div>
              </form>
            )}
          </article>
        </div>
      ) : null}
    </section>
  );
}

function CalendarView({ userId }: { userId: number }) {
  const [viewMode, setViewMode] = useState<CalendarViewMode>("month");
  const [currentDate, setCurrentDate] = useState<Date>(new Date());
  const [selectedDate, setSelectedDate] = useState<string>(toIsoDate(new Date()));
  const [statusFilter, setStatusFilter] = useState("");
  const [crewFilter, setCrewFilter] = useState("");
  const [calendarData, setCalendarData] = useState<CalendarJobsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alertSettings, setAlertSettings] = useState<WorkflowAlertSettings>(() => readWorkflowAlertSettings(userId));

  const currentDateKey = toIsoDate(currentDate);
  const range = calendarRange(currentDate, viewMode);

  const loadCalendar = async (refreshOnly: boolean) => {
    try {
      if (refreshOnly) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      const payload = await getCalendarJobs({
        start_date: range.start,
        end_date: range.end,
        status: statusFilter || undefined,
        crew: crewFilter || undefined,
      });
      setCalendarData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load calendar jobs");
    } finally {
      if (refreshOnly) {
        setRefreshing(false);
      } else {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void loadCalendar(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range.start, range.end, statusFilter, crewFilter, userId]);

  useEffect(() => {
    setAlertSettings(readWorkflowAlertSettings(userId));
  }, [userId]);

  useEffect(() => {
    setSelectedDate(currentDateKey);
  }, [currentDateKey]);

  const movePeriod = (delta: number) => {
    setCurrentDate((prev) => {
      const next = new Date(prev.getFullYear(), prev.getMonth(), prev.getDate());
      if (viewMode === "month") {
        next.setMonth(next.getMonth() + delta);
      } else if (viewMode === "week") {
        next.setDate(next.getDate() + delta * 7);
      } else {
        next.setDate(next.getDate() + delta);
      }
      return next;
    });
  };

  const jobsByDate = new Map<string, CalendarJobItem[]>();
  for (const job of calendarData?.jobs ?? []) {
    for (const dateKey of jobDateKeys(job)) {
      if (dateKey < range.start || dateKey > range.end) {
        continue;
      }
      const existing = jobsByDate.get(dateKey) ?? [];
      if (!existing.some((candidate) => candidate.job_id === job.job_id)) {
        existing.push(job);
      }
      jobsByDate.set(dateKey, existing);
    }
  }

  const selectedJobs = jobsByDate.get(selectedDate) ?? [];

  const renderJobCard = (job: CalendarJobItem) => {
    const workflowAlert = evaluateWorkflowAlert(job, alertSettings);
    return (
      <article
        key={`${job.job_id}-${job.status}`}
        className={`calendar-job-card status-${job.status}${workflowAlertLevelClass(workflowAlert)}`}
      >
        <div className="job-primary">
          <strong>{job.project_name}</strong>
          <div className="job-status-row">
            <span className="job-status-chip">{job.status_display}</span>
            {workflowAlert !== "none" ? (
              <span className={`job-alert-chip ${workflowAlert}`}>{workflowAlertLabel(workflowAlert)}</span>
            ) : null}
          </div>
        </div>
        <div className="job-secondary">
          <span>{money.format(job.bid_amount || 0)}</span>
          <span>{formatDate(job.scheduled_date)}</span>
        </div>
        {job.assigned_crew.length > 0 ? (
          <p className="calendar-job-crew">Crew: {job.assigned_crew.join(", ")}</p>
        ) : null}
      </article>
    );
  };

  const renderMonthView = () => {
    const monthStart = startOfMonth(currentDate);
    const daysInMonth = endOfMonth(currentDate).getDate();
    const startOffset = (monthStart.getDay() + 6) % 7;

    const cells: Array<Date | null> = [];
    for (let i = 0; i < startOffset; i += 1) {
      cells.push(null);
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
      cells.push(new Date(currentDate.getFullYear(), currentDate.getMonth(), day));
    }
    while (cells.length % 7 !== 0) {
      cells.push(null);
    }

    return (
      <div className="calendar-month-grid">
        {calendarWeekdays.map((label) => (
          <div key={label} className="calendar-weekday">{label}</div>
        ))}
        {cells.map((cellDate, index) => {
          if (!cellDate) {
            return <div key={`empty-${index}`} className="calendar-day-cell calendar-day-empty" />;
          }

          const dateKey = toIsoDate(cellDate);
          const dayJobs = jobsByDate.get(dateKey) ?? [];
          const isToday = dateKey === toIsoDate(new Date());
          const isSelected = dateKey === selectedDate;

          return (
            <button
              key={dateKey}
              className={`calendar-day-cell${isToday ? " today" : ""}${isSelected ? " selected" : ""}`}
              type="button"
              onClick={() => setSelectedDate(dateKey)}
            >
              <span className="calendar-day-number">{cellDate.getDate()}</span>
              <div className="calendar-day-jobs">
                {dayJobs.slice(0, 2).map((job) => (
                  <span
                    key={`${dateKey}-${job.job_id}`}
                    className={`calendar-job-pill status-${job.status}${workflowAlertLevelClass(
                      evaluateWorkflowAlert(job, alertSettings),
                    )}`}
                  >
                    {job.project_name}
                  </span>
                ))}
                {dayJobs.length > 2 ? <span className="calendar-more-pill">+{dayJobs.length - 2} more</span> : null}
              </div>
            </button>
          );
        })}
      </div>
    );
  };

  const renderWeekView = () => {
    const weekStart = startOfWeek(currentDate);
    const days = Array.from({ length: 7 }, (_, index) => addDays(weekStart, index));

    return (
      <div className="calendar-week-grid">
        {days.map((day) => {
          const dateKey = toIsoDate(day);
          const dayJobs = jobsByDate.get(dateKey) ?? [];
          const isToday = dateKey === toIsoDate(new Date());
          return (
            <section key={dateKey} className={`calendar-week-column${isToday ? " today" : ""}`}>
              <button
                className="calendar-week-header"
                type="button"
                onClick={() => setSelectedDate(dateKey)}
              >
                <strong>{calendarWeekdays[(day.getDay() + 6) % 7]}</strong>
                <span>{day.toLocaleDateString()}</span>
              </button>
              <div className="calendar-week-jobs">
                {dayJobs.length > 0 ? dayJobs.map((job) => renderJobCard(job)) : <p className="calendar-empty-day">No jobs</p>}
              </div>
            </section>
          );
        })}
      </div>
    );
  };

  const renderDayView = () => {
    const dayJobs = jobsByDate.get(currentDateKey) ?? [];
    return (
      <section className="calendar-day-view">
        {dayJobs.length > 0 ? dayJobs.map((job) => renderJobCard(job)) : <p>No jobs scheduled for this day.</p>}
      </section>
    );
  };

  const title =
    viewMode === "month"
      ? currentDate.toLocaleDateString(undefined, { month: "long", year: "numeric" })
      : viewMode === "week"
        ? `${startOfWeek(currentDate).toLocaleDateString()} - ${endOfWeek(currentDate).toLocaleDateString()}`
        : currentDate.toLocaleDateString(undefined, {
            weekday: "long",
            month: "long",
            day: "numeric",
            year: "numeric",
          });

  if (loading) {
    return <section className="panel"><p>Loading calendar...</p></section>;
  }

  if (!calendarData) {
    return (
      <section className="panel">
        <h2>Calendar Error</h2>
        <p>{error ?? "No calendar data available."}</p>
        <button className="nav-item" onClick={() => void loadCalendar(false)} type="button">
          Retry
        </button>
      </section>
    );
  }

  return (
    <section className="panel-stack calendar-shell">
      <article className="panel calendar-header-panel">
        <div className="calendar-nav-row">
          <div className="calendar-nav-controls">
            <button className="nav-item compact" type="button" onClick={() => movePeriod(-1)}>
              Prev
            </button>
            <button className="nav-item compact" type="button" onClick={() => setCurrentDate(new Date())}>
              Today
            </button>
            <button className="nav-item compact" type="button" onClick={() => movePeriod(1)}>
              Next
            </button>
            <h2>{title}</h2>
          </div>

          <div className="calendar-view-toggle">
            {(["month", "week", "day"] as CalendarViewMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                className={`nav-item compact${viewMode === mode ? " active" : ""}`}
                onClick={() => setViewMode(mode)}
              >
                {mode[0].toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="calendar-filter-row">
          <label>
            Status
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All</option>
              <option value="awaiting_approval">Awaiting Approval</option>
              <option value="scheduled">Scheduled</option>
              <option value="in_progress">In Progress</option>
              <option value="inspection">Inspection</option>
              <option value="completed">Completed</option>
              <option value="invoiced">Invoiced</option>
            </select>
          </label>
          <label>
            Crew
            <select value={crewFilter} onChange={(e) => setCrewFilter(e.target.value)}>
              <option value="">All Crew</option>
              {calendarData.available_crews.map((crew) => (
                <option key={crew} value={crew}>{crew}</option>
              ))}
            </select>
          </label>
          <button
            className="nav-item compact"
            type="button"
            onClick={() => void loadCalendar(true)}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </article>

      {error ? <article className="panel error-panel"><p>{error}</p></article> : null}

      <article className="panel calendar-main-panel">
        {viewMode === "month" ? renderMonthView() : null}
        {viewMode === "week" ? renderWeekView() : null}
        {viewMode === "day" ? renderDayView() : null}
      </article>

      <article className="panel">
        <h2>Jobs on {fromIsoDate(selectedDate).toLocaleDateString()}</h2>
        {selectedJobs.length > 0 ? (
          <div className="calendar-selected-list">{selectedJobs.map((job) => renderJobCard(job))}</div>
        ) : (
          <p>No jobs mapped to this date.</p>
        )}
      </article>
    </section>
  );
}

function PlaceholderView({ title, message }: { title: string; message: string }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <p>{message}</p>
    </section>
  );
}

function summarizeReadinessFailure(report: HealthReadinessResponse): string {
  const failingRequiredChecks = Object.entries(report.checks).filter(
    ([, check]) => check.required && check.status === "fail",
  );

  if (failingRequiredChecks.length > 0) {
    return failingRequiredChecks.map(([key, check]) => `${key}: ${check.message}`).join(" | ");
  }

  const degradedChecks = Object.entries(report.checks).filter(([, check]) => check.status === "degraded");
  if (degradedChecks.length > 0) {
    return degradedChecks.map(([key, check]) => `${key}: ${check.message}`).join(" | ");
  }

  return "Backend is still starting. Please retry.";
}

function App() {
  const [health, setHealth] = useState("starting");
  const [startupState, setStartupState] = useState<"checking" | "ready" | "error">("checking");
  const [startupMessage, setStartupMessage] = useState<string>("Checking backend readiness...");
  const [activeView, setActiveView] = useState<NavKey>("dashboard");
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authNotice, setAuthNotice] = useState<string | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const authShellRef = useRef<HTMLDivElement | null>(null);
  const authPointerTargetRef = useRef({ x: 52, y: 28 });
  const authPointerCurrentRef = useRef({ x: 52, y: 28 });
  const authPointerRafRef = useRef<number | null>(null);
  const lastActivityPersistAtRef = useRef(0);

  const runStartupReadinessCheck = async () => {
    setStartupState("checking");
    setStartupMessage("Checking backend readiness...");
    try {
      const report = await getHealthReadiness();
      setHealth(report.status);
      if (report.ready) {
        setStartupState("ready");
        return;
      }
      setStartupState("error");
      setStartupMessage(summarizeReadinessFailure(report));
    } catch (err) {
      setHealth("offline");
      setStartupState("error");
      setStartupMessage(err instanceof Error ? err.message : "Failed to reach backend readiness endpoint.");
    }
  };

  useEffect(() => {
    void runStartupReadinessCheck();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const session = readAuthSessionFromStorage();
    if (!session) {
      return;
    }
    if (isAuthSessionExpired(session)) {
      clearAuthSessionFromStorage();
      setAuthNotice("Session expired. Please sign in again.");
      return;
    }
    writeAuthSessionToStorage(withSessionActivity(session));
    setAuthToken(session.user.access_token);
    setAuthUser(session.user);
  }, []);

  useEffect(() => {
    setAuthFailureHandler((message: string) => {
      setAuthToken(null);
      setAuthUser(null);
      clearAuthSessionFromStorage();
      setAuthNotice(message || "Session expired. Please sign in again.");
    });
    return () => {
      setAuthFailureHandler(null);
    };
  }, []);

  const handleAuthenticated = (user: AuthUser) => {
    setAuthUser(user);
    setAuthToken(user.access_token);
    setAuthNotice(null);
    writeAuthSessionToStorage(buildAuthSession(user));
    lastActivityPersistAtRef.current = Date.now();
    setActiveView("dashboard");
  };

  const handleLogout = (notice?: string) => {
    if (authUser?.access_token) {
      void logoutSession().catch(() => undefined);
    }
    setAuthToken(null);
    setAuthUser(null);
    clearAuthSessionFromStorage();
    setAuthNotice(notice ?? null);
  };

  useEffect(() => {
    if (!authUser) {
      return;
    }

    const persistActivity = () => {
      const nowMs = Date.now();
      if (nowMs - lastActivityPersistAtRef.current < AUTH_ACTIVITY_PERSIST_MS) {
        return;
      }
      const session = readAuthSessionFromStorage();
      if (!session) {
        return;
      }
      writeAuthSessionToStorage(withSessionActivity(session, nowMs));
      lastActivityPersistAtRef.current = nowMs;
    };

    const onActivity = () => persistActivity();
    const activityEvents: Array<keyof WindowEventMap> = [
      "pointerdown",
      "pointermove",
      "keydown",
      "scroll",
      "touchstart",
    ];
    activityEvents.forEach((eventName) => {
      window.addEventListener(eventName, onActivity, { passive: true });
    });

    const intervalId = window.setInterval(() => {
      const session = readAuthSessionFromStorage();
      if (!session || isAuthSessionExpired(session)) {
        handleLogout("Session expired. Please sign in again.");
      }
    }, 15_000);

    return () => {
      window.clearInterval(intervalId);
      activityEvents.forEach((eventName) => {
        window.removeEventListener(eventName, onActivity);
      });
    };
  }, [authUser]);

  useEffect(() => {
    if (authUser) {
      if (authPointerRafRef.current !== null) {
        window.cancelAnimationFrame(authPointerRafRef.current);
        authPointerRafRef.current = null;
      }
      return;
    }

    const step = () => {
      const shell = authShellRef.current;
      if (shell) {
        const target = authPointerTargetRef.current;
        const current = authPointerCurrentRef.current;
        current.x += (target.x - current.x) * 0.16;
        current.y += (target.y - current.y) * 0.16;
        shell.style.setProperty("--auth-pointer-x", `${current.x.toFixed(2)}%`);
        shell.style.setProperty("--auth-pointer-y", `${current.y.toFixed(2)}%`);
      }
      authPointerRafRef.current = window.requestAnimationFrame(step);
    };

    authPointerRafRef.current = window.requestAnimationFrame(step);
    return () => {
      if (authPointerRafRef.current !== null) {
        window.cancelAnimationFrame(authPointerRafRef.current);
        authPointerRafRef.current = null;
      }
    };
  }, [authUser]);

  const handleAuthPointerMove = (event: MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      return;
    }
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    authPointerTargetRef.current = { x, y };
  };

  const resetAuthPointer = () => {
    authPointerTargetRef.current = { x: 52, y: 28 };
  };
  const healthLabel = health === "ok" ? "ready" : health;

  if (startupState !== "ready") {
    return (
      <div
        ref={authShellRef}
        className="auth-only-shell"
        onMouseMove={handleAuthPointerMove}
        onMouseLeave={resetAuthPointer}
      >
        <AuthNetworkBackground />
        <main className="content auth-content">
          <header className="topbar">
            <div className="status-pill">API: {healthLabel}</div>
          </header>
          <section className="auth-shell">
            <article className={`panel auth-card${startupState === "error" ? " error-panel" : ""}`}>
              <h2>{startupState === "checking" ? "Starting backend..." : "Backend not ready"}</h2>
              <p>
                {startupState === "checking"
                  ? "Waiting for /health/ready before enabling the app."
                  : startupMessage}
              </p>
              {startupState === "error" ? (
                <button
                  className="nav-item primary-action"
                  type="button"
                  onClick={() => void runStartupReadinessCheck()}
                >
                  Retry Readiness Check
                </button>
              ) : null}
            </article>
          </section>
        </main>
      </div>
    );
  }

  if (!authUser) {
    return (
      <div
        ref={authShellRef}
        className="auth-only-shell"
        onMouseMove={handleAuthPointerMove}
        onMouseLeave={resetAuthPointer}
      >
        <AuthNetworkBackground />
        <main className="content auth-content">
          <header className="topbar">
            <div className="status-pill">API: {healthLabel}</div>
          </header>
          <AuthView onAuthenticated={handleAuthenticated} sessionNotice={authNotice} />
        </main>
      </div>
    );
  }

  return (
    <div className={`app-shell${isSidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="sidebar-brand-row">
          <h1>{isSidebarCollapsed ? "LB" : "LightningBid"}</h1>
          <button
            className="sidebar-toggle"
            type="button"
            onClick={() => setIsSidebarCollapsed((prev) => !prev)}
            aria-label={isSidebarCollapsed ? "Expand navigation sidebar" : "Collapse navigation sidebar"}
          >
            {isSidebarCollapsed ? ">" : "<"}
          </button>
        </div>
        <nav>
          {navItems.map((item) => (
            <button
              key={item.key}
              className={`nav-item${activeView === item.key ? " active" : ""}`}
              onClick={() => setActiveView(item.key)}
              title={isSidebarCollapsed ? item.label : undefined}
              type="button"
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <main className="content">
        <header className="topbar">
          <div className="status-pill">User: {authUser.username}</div>
          <button className="nav-item compact" type="button" onClick={() => handleLogout()}>Logout</button>
          <div className="status-pill">API: {healthLabel}</div>
        </header>

        {activeView === "dashboard" ? <DashboardView onNavigate={setActiveView} userId={authUser.user_id} /> : null}
        {activeView === "bidding" ? <BiddingView userId={authUser.user_id} /> : null}
        {activeView === "jobs" ? <JobsView userId={authUser.user_id} username={authUser.username} /> : null}
        {activeView === "calendar" ? <CalendarView userId={authUser.user_id} /> : null}
        {activeView === "reports" ? (
          <PlaceholderView
            title="Reports Migration"
            message="Next step: port revenue/profit reporting and export workflow."
          />
        ) : null}
      </main>
    </div>
  );
}

export default App;
