import type { CitationSource } from './store';

const STORAGE_BASE_URL = 'https://pobgqxhneruhswxedqpf.supabase.co/storage/v1/object/public/panduan-dokumen/';

export interface DocumentSource {
  id: string;
  title: string;
  fileUrl: string;
}

export const DOCUMENTS: DocumentSource[] = [
  { id: 'pi', title: 'Panduan Penulisan Ilmiah (PI)', fileUrl: `${STORAGE_BASE_URL}panduan-pi.pdf` },
  { id: 'kkp', title: 'Panduan Kuliah Kerja Praktik (KKP)', fileUrl: `${STORAGE_BASE_URL}panduan-kkp.pdf` },
  { id: 'skripsi', title: 'Panduan Skripsi', fileUrl: `${STORAGE_BASE_URL}panduan-skripsi.pdf` },
  { id: 'non-skripsi', title: 'Panduan Non-Skripsi', fileUrl: `${STORAGE_BASE_URL}panduan-non-skripsi.pdf` }
];
/** Resolve explicit provenance; unknown sources must not silently open Skripsi. */
export function resolveCitationUrl(source: CitationSource | string): string | null {
  const src = typeof source === 'string' ? { title: source } : source;
  const normalize = (value: string) => value.toLowerCase().replace(/[_\s]+/g, '-');
  let domain: string | undefined;
  const explicit = normalize(src.domain || '');
  if (DOCUMENTS.some(doc => doc.id === explicit)) domain = explicit;
  const candidates = [src.source, src.parent_id, src.title, src.section];
  for (const value of candidates) {
    if (domain) break;
    if (!value) continue;
    const label = normalize(value);
    if (/non-?skripsi|\bptans-/.test(label)) domain = 'non-skripsi';
    else if (/skripsi|\bptas-/.test(label)) domain = 'skripsi';
    else if (/(?:^|-)kkp(?:-|$)|kuliah-kerja/.test(label)) domain = 'kkp';
    else if (/(?:^|-)pi(?:-|$)|penulisan-ilmiah|penulisan-imliah/.test(label)) domain = 'pi';
  }
  if (!domain) return null;
  const document = DOCUMENTS.find(doc => doc.id === domain);
  if (!document) return null;
  // Existing chunk pages are PRINTED page labels, not PDF viewer indices.
  // Navigate by #page only when an explicit PDF index is available.
  const page = src.pdf_pages?.find(page => Number.isInteger(page) && page > 0);
  if (page) return `${document.fileUrl}#page=${page}`;
  const term = src.title || src.section;
  return term ? `${document.fileUrl}#search=${encodeURIComponent(term.split(' ').slice(0, 8).join(' '))}` : document.fileUrl;
}
