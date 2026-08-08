const STORAGE_BASE_URL = 'https://pobgqxhneruhswxedqpf.supabase.co/storage/v1/object/public/panduan-dokumen/';

export interface DocumentSource {
  id: string;
  title: string;
  fileUrl: string;
}

export const DOCUMENTS: DocumentSource[] = [
  { id: 'pi', title: 'Panduan Praktik Industri (PI)', fileUrl: `${STORAGE_BASE_URL}panduan-pi.pdf` },
  { id: 'kkp', title: 'Panduan Kuliah Kerja Praktik (KKP)', fileUrl: `${STORAGE_BASE_URL}panduan-kkp.pdf` },
  { id: 'skripsi', title: 'Panduan Skripsi', fileUrl: `${STORAGE_BASE_URL}panduan-skripsi.pdf` },
  { id: 'non-skripsi', title: 'Panduan Non-Skripsi', fileUrl: `${STORAGE_BASE_URL}panduan-non-skripsi.pdf` }
];
