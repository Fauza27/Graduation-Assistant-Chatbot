import type {
  Domain,
  ErrorSource,
  QueryLogRow,
  RequestStatus,
  StageKey,
} from "./monitoringTypes";
import { PIPELINE_STAGE_KEYS } from "./monitoringTypes";

// ============================================================
// Status di UI mengikuti hasil request yang benar-benar dicatat backend.
// Latency tetap ditampilkan sebagai angka dan grafik tersendiri; jangan
// mengubah request sukses menjadi status gagal hanya karena melewati ambang
// waktu visual yang arbitrer.
// ============================================================

export type DisplayStatus = "success" | "timeout" | "error" | "quota_rejected";

/** Derivasi status tampilan dari status asli + latency + error_type. */
export function deriveDisplayStatus(row: {
  status: RequestStatus;
  total_ms: number | null;
  error_type: string | null;
}): DisplayStatus {
  if (row.status === "quota_rejected") return "quota_rejected";
  if (row.status === "error") {
    const t = (row.error_type || "").toLowerCase();
    if (t.includes("timeout")) return "timeout";
    return "error";
  }
  return "success";
}

export const STATUS_BADGE_CLASS: Record<DisplayStatus, string> = {
  success: "status-success",
  timeout: "status-danger",
  error: "status-danger",
  quota_rejected: "status-warning",
};

export const STATUS_LABEL: Record<DisplayStatus, string> = {
  success: "Success",
  timeout: "Timeout",
  error: "Error",
  quota_rejected: "Kuota Habis",
};

const DOMAIN_LABELS: Record<string, string> = {
  PI: "PI",
  KKP: "KKP",
  SKRIPSI: "Skripsi",
  NON_SKRIPSI: "Non-Skripsi",
  UNKNOWN: "Lainnya",
};

export function formatDomain(domain: Domain): string {
  if (!domain) return "Lainnya";
  return DOMAIN_LABELS[domain] || domain;
}

export function formatChannel(channel: string | null | undefined): string {
  if (channel === "website") return "Website";
  if (channel === "telegram") return "Telegram";
  return channel || "Lainnya";
}

// error_source + error_type mentah -> label & detail yang enak dibaca manusia.
// Backend belum menyimpan pesan error mentah (str(exception)) secara terpisah,
// jadi detail di sini disusun dari kombinasi source+type yang SUDAH ada.
const ERROR_SOURCE_LABELS: Record<string, string> = {
  openai: "OpenAI API Error",
  supabase: "Supabase Error",
  validation: "Validation Error",
  rate_limit: "Rate Limit OpenAI",
  unknown: "Error Tidak Diketahui",
};

export function formatErrorSource(source: ErrorSource): string {
  if (!source) return "Error Tidak Diketahui";
  return ERROR_SOURCE_LABELS[source] || source;
}

export function deriveErrorDetail(
  source: ErrorSource,
  errorType: string | null,
): string {
  if (!source)
    return errorType || "Terjadi kesalahan yang tidak terklasifikasi.";
  const type = errorType || "";
  if (type.toLowerCase().includes("timeout"))
    return `${type} — permintaan melebihi batas waktu.`;
  if (source === "rate_limit")
    return "Permintaan ditolak OpenAI karena rate limit tercapai.";
  if (source === "validation") return type || "Payload request tidak valid.";
  return type || `Kesalahan dari sisi ${formatErrorSource(source)}.`;
}

export type Severity = "info" | "warn" | "crit";

/** source -> tingkat keparahan, dipakai badge & pengelompokan di log error. */
export function deriveSeverity(source: ErrorSource): Severity {
  if (source === "supabase") return "crit";
  if (source === "openai") return "warn";
  return "info";
}

// ============================================================
// Angka & tanggal
// ============================================================
export function fmtThousand(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export function fmtCompact(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  const v = Math.round(n);
  if (Math.abs(v) >= 1000)
    return (v / 1000).toFixed(v % 1000 === 0 ? 0 : 1).replace(".", ",") + "rb";
  return String(v);
}

export function fmtMs(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${Math.round(n)} ms`;
}

export function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(digits)}%`;
}

export function fmtUsd(n: number | null | undefined, digits = 4): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `$${n.toFixed(digits)}`;
}

export function fmtDateShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("id-ID", { day: "numeric", month: "short" });
}

export function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const date = d.toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const time = d.toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${date} ${time}`;
}

/** Rentang "N hari terakhir" -> tanggal since dalam format ISO (dipakai query param). */
export function daysAgoIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString();
}

// ============================================================
// Pipeline helpers
// ============================================================
export function totalStageMs(row: Pick<QueryLogRow, StageKey>): number {
  return PIPELINE_STAGE_KEYS.reduce((sum, key) => sum + (row[key] ?? 0), 0);
}

export function shortId(id: string | null | undefined, len = 8): string {
  if (!id) return "—";
  return id.length > len ? `${id.slice(0, len)}…` : id;
}
