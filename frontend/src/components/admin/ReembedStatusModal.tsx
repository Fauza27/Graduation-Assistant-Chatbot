"use client";

import { useState, useEffect, useRef } from "react";
import { AlertCircle, CheckCircle2, X } from "lucide-react";
import { triggerReembed, getEditStatus } from "@/lib/adminApi";
import { EmbeddingStatus, EditLogStatus } from "@/lib/adminTypes";

interface ReembedStatusModalProps {
  childId: string;
  onDone: (finalStatus: EmbeddingStatus) => void;
  onClose: () => void;
}

export default function ReembedStatusModal({ childId, onDone, onClose }: ReembedStatusModalProps) {
  const [logStatus, setLogStatus] = useState<EditLogStatus | "starting" | null>("starting");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const isBusy = logStatus === "starting" || logStatus === "pending" || logStatus === "processing";

  const getStatusLabel = () => {
    if (logStatus === "failed") return "Gagal";
    if (logStatus === "success") return "Selesai";
    if (logStatus === "processing") return "Memproses";
    if (logStatus === "pending") return "Dalam antrean";
    return "Memulai";
  };

  const getProgress = () => {
    if (logStatus === "failed") return 100;
    if (logStatus === "success") return 100;
    if (logStatus === "processing") return 72;
    if (logStatus === "pending") return 40;
    return 14;
  };

  // Start reembed process when modal opens
  useEffect(() => {
    const initializeReembed = async () => {
      setLogStatus("starting");
      setErrorMessage(null);
      try {
        const res = await triggerReembed(childId);
        setLogStatus(res.status);
      } catch (err: Error | unknown) {
        const errorMessage = err instanceof Error ? err.message : "Gagal memulai proses re-embed.";
        setLogStatus("failed");
        setErrorMessage(errorMessage);
      }
    };
    
    initializeReembed();
    
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [childId]);

  useEffect(() => {
    if (logStatus === "pending" || logStatus === "processing") {
      pollingRef.current = setInterval(async () => {
        try {
          const res = await getEditStatus(childId);
          setLogStatus(res.status);
          if (res.status === "success" || res.status === "failed") {
            if (pollingRef.current) clearInterval(pollingRef.current);
            if (res.status === "failed") {
              setErrorMessage(res.error_message || "Gagal saat memproses re-embed.");
            }
            onDone(res.status === "success" ? "success" : "failed");
          }
        } catch {
          // Keep polling unless it fails hard, but we assume transient network errors
        }
      }, 1500);
    }

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [logStatus, childId, onDone]);

  // Mapping status to UI step states
  // Step 1: Antrean (pending)
  // Step 2: Processing (processing)
  // Step 3: Success (success)

  const getStepClass = (step: number) => {
    if (logStatus === "failed") return ""; // All steps lose active visual if failed

    if (step === 1) {
      if (logStatus === "success" || logStatus === "processing") return "done";
      if (logStatus === "pending" || logStatus === "starting") return "active";
    }
    if (step === 2) {
      if (logStatus === "success") return "done";
      if (logStatus === "processing") return "active";
    }
    if (step === 3) {
      if (logStatus === "success") return "done";
    }
    return "";
  };

  return (
    <div className="modal-overlay show">
      <div className="modal-card">
        <div className="modal-head">
          <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
            <h3 style={{ marginBottom: 0 }}>Sinkronisasi Vector DB</h3>
            <span className={`status-badge ${logStatus === "failed" ? "status-danger" : logStatus === "success" ? "status-success" : "status-info"}`} style={{ width: "fit-content" }}>
              {getStatusLabel()}
            </span>
          </div>
          <button className="icon-btn icon-btn-sm" onClick={onClose} disabled={isBusy} type="button" aria-label={isBusy ? "Proses sedang berjalan" : "Tutup"} title={isBusy ? "Tunggu sampai proses selesai" : "Tutup"}>
            <X className="icon-xs" />
          </button>
        </div>
        <p className="modal-sub" style={{ marginBottom: 14 }}>
          Chunk <strong>{childId.substring(0, 12)}...</strong> sedang disinkronkan ke Vector DB. Tutup modal setelah status selesai.
        </p>

        <div style={{ width: "100%", height: 6, borderRadius: 999, background: "var(--gray-100)", overflow: "hidden", marginBottom: 14 }}>
          <div
            style={{
              width: `${getProgress()}%`,
              height: "100%",
              borderRadius: 999,
              background: logStatus === "failed" ? "var(--danger)" : "var(--purple-primary)",
              transition: "width .25s ease",
            }}
          />
        </div>

        {logStatus === "failed" ? (
          <div className="empty-state" style={{ padding: "16px 0" }}>
            <div className="modal-danger-icon" style={{ marginBottom: "10px" }}>
              <AlertCircle size={24} />
            </div>
            <h3 style={{ color: "var(--danger)" }}>Re-embed Gagal</h3>
            <p>{errorMessage}</p>
          </div>
        ) : (
          <div className="reembed-steps">
            <div className={`reembed-step ${getStepClass(1)}`}>
              <div className="step-dot">1</div>
              <div className="step-info">
                <div className="step-title">Dalam Antrean</div>
                <div className="step-desc">Perubahan tersimpan, menunggu giliran diproses.</div>
              </div>
            </div>

            <div className={`reembed-step ${getStepClass(2)}`}>
              <div className="step-dot">2</div>
              <div className="step-info">
                <div className="step-title">Menghasilkan Embedding</div>
                <div className="step-desc">Menghubungi AI provider dan memperbarui penyimpanan vektor.</div>
              </div>
            </div>

            <div className={`reembed-step ${getStepClass(3)}`}>
              <div className="step-dot">3</div>
              <div className="step-info">
                <div className="step-title">Selesai</div>
                <div className="step-desc">Vector chunk telah diperbarui dan siap dipakai.</div>
              </div>
            </div>
          </div>
        )}

        {logStatus === "success" && (
          <div className="reembed-success-banner show">
            <CheckCircle2 size={16} />
            <p>Chunk berhasil disinkronisasi ke Vector DB dan langsung siap dipakai.</p>
          </div>
        )}

        <div className="modal-actions">
          {logStatus === "failed" ? (
            <>
              <button className="btn btn-outline-gray" onClick={onClose} type="button">
                Tutup
              </button>
              <button className="btn btn-primary" onClick={() => window.location.reload()} type="button">
                Coba Lagi
              </button>
            </>
          ) : (
            <button className={`btn ${logStatus === "success" ? "btn-primary" : "btn-outline-gray"}`} onClick={onClose} disabled={isBusy} type="button">
              {logStatus === "success" ? "Selesai" : "Sedang diproses"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
