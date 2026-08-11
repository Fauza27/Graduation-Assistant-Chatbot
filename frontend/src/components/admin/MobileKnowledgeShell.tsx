"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronRight, FileText, Bookmark, FileStack, ArrowLeft, Maximize2, Layers3 } from "lucide-react";
import { useAdminStore } from "@/lib/adminStore";
import ChunkDetailPanel from "./ChunkDetailPanel";

export default function MobileKnowledgeShell() {
  const router = useRouter();
  const { tree, selectChild, selectedChildId } = useAdminStore();

  // Steps: 1 (Docs), 2 (Structure), 3 (Detail)
  const [step, setStep] = useState(1);
  const [selectedDocKey, setSelectedDocKey] = useState<string | null>(null);

  if (!tree) return null;

  const currentDoc = tree.documents.find((d) => `${d.domain}-${d.source}` === selectedDocKey);

  const totalDocs = tree.documents.length;
  const totalParents = currentDoc?.chapters.reduce((sum, chapter) => sum + chapter.parents.length, 0) ?? 0;
  const totalChildren = currentDoc?.chapters.reduce((sum, chapter) => sum + chapter.parents.reduce((parentSum, parent) => parentSum + parent.children.length, 0), 0) ?? 0;

  return (
    <div className="mobile-shell">
      {/* STEP 1: Daftar Dokumen */}
      <div className={`mobile-step ${step === 1 ? "active" : ""}`}>
        <div className="mobile-topbar">
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
            <h2 style={{ textAlign: "left", margin: 0 }}>Dokumen Panduan</h2>
            <p style={{ margin: 0, fontSize: 11.5, color: "var(--gray-400)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>Pilih dokumen, lalu telusuri bab dan child chunk.</p>
          </div>
        </div>
        <div className="mobile-step-scroll">
          <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
            <span className="status-badge status-info">{totalDocs} dokumen</span>
            <span className="status-badge status-success">Langkah 1 dari 3</span>
          </div>
          {tree.documents.map((doc) => {
            const key = `${doc.domain}-${doc.source}`;
            const totalParents = doc.chapters.reduce((sum, c) => sum + c.parents.length, 0);
            const totalChildren = doc.chapters.reduce((sum, c) => sum + c.parents.reduce((parentSum, parent) => parentSum + parent.children.length, 0), 0);
            return (
              <button
                key={key}
                className="mdoc-item"
                onClick={() => {
                  setSelectedDocKey(key);
                  setStep(2);
                }}
                type="button"
              >
                <div className="mdoc-icon">
                  <FileText strokeWidth={2.5} />
                </div>
                <div className="mdoc-meta">
                  <div className="mname">{doc.source}</div>
                  <div className="mcount">
                    {doc.domain} • {totalParents} parent • {totalChildren} child
                  </div>
                </div>
                <ChevronRight className="icon-sm chev" />
              </button>
            );
          })}
        </div>
      </div>

      {/* STEP 2: Struktur / Chapters & Parents */}
      <div className={`mobile-step ${step === 2 ? "active" : ""}`}>
        <div className="mobile-topbar">
          <button className="icon-btn" onClick={() => setStep(1)} type="button">
            <ArrowLeft className="icon" />
          </button>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
            <h2 style={{ margin: 0 }}>{currentDoc?.source || "Struktur Dokumen"}</h2>
            <p style={{ margin: 0, fontSize: 11.5, color: "var(--gray-400)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {currentDoc ? `${currentDoc.domain} • ${currentDoc.chapters.length} bab • ${totalParents} parent • ${totalChildren} child` : "Pilih dokumen untuk melihat struktur."}
            </p>
          </div>
        </div>
        <div className="mobile-step-scroll" style={{ padding: "16px 12px" }}>
          {currentDoc && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, padding: "12px 14px", border: "1px solid var(--border)", borderRadius: 14, background: "var(--gray-100)" }}>
              <div className="mdoc-icon" style={{ width: 34, height: 34 }}>
                <Layers3 strokeWidth={2.2} />
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--gray-700)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{currentDoc.source}</div>
                <div style={{ fontSize: 11.5, color: "var(--gray-500)", marginTop: 2 }}>Pilih child chunk untuk membuka panel detail.</div>
              </div>
            </div>
          )}
          {currentDoc?.chapters.map((chap) => (
            <div key={chap.section} style={{ marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px", padding: "0 4px" }}>
                <Bookmark className="icon-sm" style={{ color: "var(--gray-400)" }} />
                <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--gray-500)" }}>{chap.section}</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {chap.parents.map((par) => {
                  const parKey = `${selectedDocKey}-${chap.section}-${par.parent_id}`;
                  return (
                    <div key={parKey} style={{ border: "1px solid var(--border)", borderRadius: "12px", overflow: "hidden" }}>
                      <div style={{ padding: "12px 14px", background: "var(--gray-100)", borderBottom: "1px solid var(--border)" }}>
                        <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--gray-700)", marginBottom: "4px" }}>{par.title}</div>
                        <div style={{ fontSize: "11px", color: "var(--gray-500)" }}>{par.children.length} child chunk</div>
                      </div>
                      <div style={{ padding: "6px" }}>
                        {par.children.map((child) => (
                          <button
                            key={child.id}
                            className="tree-row"
                            onClick={() => {
                              selectChild(child.id, parKey);
                              setStep(3);
                            }}
                            type="button"
                          >
                            <div className="row-icon" style={{ background: "transparent" }}>
                              <FileStack className="icon-sm" />
                            </div>
                            <div className="tlabel">{child.title}</div>
                            <ChevronRight className="icon-sm chev" style={{ color: "var(--gray-300)" }} />
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* STEP 3: Detail Child */}
      <div className={`mobile-step ${step === 3 ? "active" : ""}`}>
        <div className="mobile-topbar">
          <button className="icon-btn" onClick={() => setStep(2)} type="button">
            <ArrowLeft className="icon" />
          </button>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
            <h2 style={{ margin: 0 }}>Detail Chunk</h2>
            <p style={{ margin: 0, fontSize: 11.5, color: "var(--gray-400)" }}>Edit, simpan, lalu re-embed dari sini.</p>
          </div>
          <button
            className="icon-btn"
            style={{ marginLeft: "auto" }}
            onClick={() => {
              if (selectedChildId) {
                router.push(`/admin/dashboard/chunks/${selectedChildId}`);
              }
            }}
            type="button"
          >
            <Maximize2 className="icon" />
          </button>
        </div>
        <div style={{ display: "flex", gap: 8, padding: "12px 16px 0", flexWrap: "wrap" }}>
          <span className="status-badge status-info">Langkah 3 dari 3</span>
          {selectedChildId && <span className="status-badge status-success">Child dipilih</span>}
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <ChunkDetailPanel childId={selectedChildId} isMobileShell={true} />
        </div>
      </div>
    </div>
  );
}
