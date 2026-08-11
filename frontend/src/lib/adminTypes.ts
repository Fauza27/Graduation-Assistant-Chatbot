export type EmbeddingStatus = 'pending' | 'stale' | 'success' | 'failed';
export type EditLogStatus = 'pending' | 'processing' | 'success' | 'failed';

export interface ChildLite {
  id: string;
  title: string;
  pages: string;
  embedding_status: EmbeddingStatus;
}
export interface ParentNode {
  parent_id: string;
  title: string;
  child_count: number;
  children: ChildLite[];
}
export interface ChapterNode {
  section: string;
  parents: ParentNode[];
}
export interface DocumentNode {
  domain: string;
  source: string;
  chapters: ChapterNode[];
}
export interface SummaryStats {
  total_documents: number;
  total_parents: number;
  total_children: number;
  last_updated_at: string;
}
export interface KnowledgeTreeResponse {
  summary: SummaryStats;
  documents: DocumentNode[];
}
export interface ChunkDetail {
  id: string;
  title: string;
  pages: string;
  content: string;
  embedding_status: EmbeddingStatus;
  reembedded_at: string | null;
  parent: { parent_id: string; title: string };
  section: string;
  domain: string;
  source: string;
}
export interface ChunkEditStatus {
  log_id: string;
  child_id: string;
  status: EditLogStatus;
  error_message: string | null;
  edited_at: string;
  reembedded_at: string | null;
}
