'use client';

import { useState, useMemo, useCallback } from 'react';
import { ChevronRight, FileText, Bookmark, FileStack } from 'lucide-react';
import { KnowledgeTreeResponse, DocumentNode, ChapterNode, ParentNode } from '@/lib/adminTypes';
import { useAdminStore } from '@/lib/adminStore';

interface KnowledgeTreeColumnProps {
  tree: KnowledgeTreeResponse | null;
  query: string;
}

interface FilteredChapter extends ChapterNode {
  key: string;
}

interface ProcessedDocument {
  docKey: string;
  document: DocumentNode;
  filteredChapters: FilteredChapter[];
  totalParents: number;
  totalChildren: number;
}

function useExpansionState() {
  const [expandedDocs, setExpandedDocs] = useState<Record<string, boolean>>({});
  const [expandedChaps, setExpandedChaps] = useState<Record<string, boolean>>({});

  const toggleDoc = useCallback((docKey: string) => {
    setExpandedDocs(prev => ({ ...prev, [docKey]: !prev[docKey] }));
  }, []);

  const toggleChap = useCallback((chapKey: string) => {
    setExpandedChaps(prev => ({ ...prev, [chapKey]: !prev[chapKey] }));
  }, []);

  return { expandedDocs, expandedChaps, toggleDoc, toggleChap };
}

function matchesSearchQuery(parent: ParentNode, doc: DocumentNode, section: string, query: string): boolean {
  if (!query) return true;
  
  const searchText = `${doc.domain} ${doc.source} ${section} ${parent.title}`.toLowerCase();
  return searchText.includes(query.toLowerCase());
}

function useProcessedDocuments(tree: KnowledgeTreeResponse | null, query: string): ProcessedDocument[] {
  return useMemo(() => {
    if (!tree?.documents) return [];

    return tree.documents.map(doc => {
      const docKey = `${doc.domain}-${doc.source}`;
      
      const filteredChapters = doc.chapters
        .map(chap => {
          const chapKey = `${docKey}-${chap.section}`;
          const filteredParents = chap.parents.filter(parent => 
            matchesSearchQuery(parent, doc, chap.section, query)
          );
          return { ...chap, parents: filteredParents, key: chapKey };
        })
        .filter(chap => chap.parents.length > 0);

      const totalParents = doc.chapters.reduce((sum, chap) => sum + chap.parents.length, 0);
      const totalChildren = doc.chapters.reduce((sum, chap) => 
        sum + chap.parents.reduce((childSum, parent) => childSum + parent.children.length, 0), 0
      );

      return {
        docKey,
        document: doc,
        filteredChapters,
        totalParents,
        totalChildren
      };
    }).filter(processed => !query || processed.filteredChapters.length > 0);
  }, [tree?.documents, query]);
}

function DocumentRow({ processed, isExpanded, onToggle, hasQuery }: {
  processed: ProcessedDocument;
  isExpanded: boolean;
  onToggle: () => void;
  hasQuery: boolean;
}) {
  const { document: doc, totalParents, totalChildren } = processed;
  const shouldExpand = hasQuery || isExpanded;

  return (
    <div className="tree-doc depth-1">
      <button className="tree-row" type="button" onClick={onToggle}>
        <ChevronRight className={`icon-sm chev ${shouldExpand ? 'rot' : ''}`} />
        <div className="row-icon"><FileText /></div>
        <div className="tlabel">{doc.source} ({doc.domain})</div>
        <div className="tcount">{totalParents} parent | {totalChildren} child</div>
      </button>

      {shouldExpand && (
        <ChapterList chapters={processed.filteredChapters} docKey={processed.docKey} hasQuery={hasQuery} />
      )}
    </div>
  );
}

function ChapterList({ chapters, docKey, hasQuery }: {
  chapters: FilteredChapter[];
  docKey: string;
  hasQuery: boolean;
}) {
  const { expandedChaps, toggleChap } = useExpansionState();

  return (
    <div className="tree-children">
      {chapters.map(chap => {
        const isExpanded = !!expandedChaps[chap.key];
        const shouldExpand = hasQuery || isExpanded;
        const totalChildren = chap.parents.reduce((sum, parent) => sum + parent.children.length, 0);

        return (
          <div key={chap.key} className="tree-doc depth-2">
            <button className="tree-row" type="button" onClick={() => toggleChap(chap.key)}>
              <ChevronRight className={`icon-sm chev ${shouldExpand ? 'rot' : ''}`} />
              <div className="row-icon" style={{background: 'var(--gray-100)', color: 'var(--gray-500)'}}>
                <Bookmark />
              </div>
              <div className="tlabel">{chap.section}</div>
              <div className="tcount">{chap.parents.length} parent | {totalChildren} child</div>
            </button>

            {shouldExpand && (
              <ParentList parents={chap.parents} docKey={docKey} section={chap.section} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function ParentList({ parents, docKey, section }: {
  parents: ParentNode[];
  docKey: string;
  section: string;
}) {
  const { selectedParentKey, selectChild } = useAdminStore();

  return (
    <div className="tree-children">
      {parents.map(parent => {
        const parentKey = `${docKey}-${section}-${parent.parent_id}`;
        const isSelected = selectedParentKey === parentKey;

        return (
          <div key={parentKey} className="tree-doc depth-3">
            <button 
              className={`tree-row ${isSelected ? 'selected' : ''}`}
              type="button"
              onClick={() => selectChild(null, parentKey)}
            >
              <div className="row-icon"><FileStack /></div>
              <div className="tlabel" title={parent.title}>{parent.title}</div>
              <div className="tcount">{parent.child_count} child</div>
            </button>
          </div>
        );
      })}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-icon"><FileStack /></div>
      <h3>Belum ada data</h3>
      <p>Knowledge base saat ini kosong atau sedang dimuat.</p>
    </div>
  );
}

export default function KnowledgeTreeColumn({ tree, query }: KnowledgeTreeColumnProps) {
  const { expandedDocs, toggleDoc } = useExpansionState();
  const processedDocuments = useProcessedDocuments(tree, query);

  if (!tree?.documents) {
    return <EmptyState />;
  }

  const hasQuery = !!query.trim();

  return (
    <>
      {processedDocuments.map(processed => (
        <DocumentRow
          key={processed.docKey}
          processed={processed}
          isExpanded={!!expandedDocs[processed.docKey]}
          onToggle={() => toggleDoc(processed.docKey)}
          hasQuery={hasQuery}
        />
      ))}
    </>
  );
}
