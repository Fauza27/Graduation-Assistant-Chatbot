'use client';

import { useState } from 'react';
import { ChevronRight, FileText, Bookmark, FileStack } from 'lucide-react';
import { KnowledgeTreeResponse } from '@/lib/adminTypes';
import { useAdminStore } from '@/lib/adminStore';

interface KnowledgeTreeColumnProps {
  tree: KnowledgeTreeResponse | null;
  query: string;
}

export default function KnowledgeTreeColumn({ tree, query }: KnowledgeTreeColumnProps) {
  const { selectedParentKey, selectChild } = useAdminStore();
  const [expandedDocs, setExpandedDocs] = useState<Record<string, boolean>>({});
  const [expandedChaps, setExpandedChaps] = useState<Record<string, boolean>>({});

  const toggleDoc = (docKey: string) => setExpandedDocs(prev => ({ ...prev, [docKey]: !prev[docKey] }));
  const toggleChap = (chapKey: string) => setExpandedChaps(prev => ({ ...prev, [chapKey]: !prev[chapKey] }));

  if (!tree || !tree.documents) {
    return (
      <div className="empty-state">
        <div className="empty-icon"><FileStack /></div>
        <h3>Belum ada data</h3>
        <p>Knowledge base saat ini kosong atau sedang dimuat.</p>
      </div>
    );
  }

  const q = query.toLowerCase();

  return (
    <>
      {tree.documents.map(doc => {
        const docKey = `${doc.domain}-${doc.source}`;
        const isDocExpanded = !!expandedDocs[docKey];
        
        // Filter chapters
        const filteredChapters = doc.chapters.map(chap => {
          const chapKey = `${docKey}-${chap.section}`;
          const filteredParents = chap.parents.filter(par => {
            const txt = (doc.domain + ' ' + doc.source + ' ' + chap.section + ' ' + par.title).toLowerCase();
            return txt.includes(q);
          });
          return { ...chap, parents: filteredParents, key: chapKey };
        }).filter(chap => chap.parents.length > 0);

        if (filteredChapters.length === 0 && q) return null;

        // Auto-expand if searching
        const effectiveDocExpanded = q ? true : isDocExpanded;

        return (
          <div key={docKey} className="tree-doc depth-1">
            <button 
              className="tree-row" 
              type="button"
              onClick={() => toggleDoc(docKey)}
            >
              <ChevronRight className={`icon-sm chev ${effectiveDocExpanded ? 'rot' : ''}`} />
              <div className="row-icon"><FileText /></div>
              <div className="tlabel">{doc.source} ({doc.domain})</div>
              <div className="tcount">
                {doc.chapters.reduce((sum, c) => sum + c.parents.length, 0)} parent | {doc.chapters.reduce((sum, c) => sum + c.parents.reduce((s, p) => s + p.children.length, 0), 0)} child
              </div>
            </button>

            {effectiveDocExpanded && (
              <div className="tree-children">
                {filteredChapters.map(chap => {
                  const isChapExpanded = !!expandedChaps[chap.key];
                  const effectiveChapExpanded = q ? true : isChapExpanded;

                  return (
                    <div key={chap.key} className="tree-doc depth-2">
                      <button 
                        className="tree-row" 
                        type="button"
                        onClick={() => toggleChap(chap.key)}
                      >
                        <ChevronRight className={`icon-sm chev ${effectiveChapExpanded ? 'rot' : ''}`} />
                        <div className="row-icon" style={{background: 'var(--gray-100)', color: 'var(--gray-500)'}}>
                          <Bookmark />
                        </div>
                        <div className="tlabel">{chap.section}</div>
                        <div className="tcount">{chap.parents.length} parent | {chap.parents.reduce((s, p) => s + p.children.length, 0)} child</div>
                      </button>

                      {effectiveChapExpanded && (
                        <div className="tree-children">
                          {chap.parents.map(par => {
                            const parKey = `${docKey}-${chap.section}-${par.parent_id}`;
                            const isSelected = selectedParentKey === parKey;

                            return (
                              <div key={parKey} className="tree-doc depth-3">
                                <button 
                                  className={`tree-row ${isSelected ? 'selected' : ''}`}
                                  type="button"
                                  onClick={() => selectChild(null, parKey)}
                                >
                                  <div className="row-icon"><FileStack /></div>
                                  <div className="tlabel" title={par.title}>{par.title}</div>
                                  <div className="tcount">{par.child_count} child</div>
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}
