'use client';

import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { adminFetch } from '@/lib/adminApi';
import { resolveCitationUrl } from '@/lib/documentSources';
import {
  buildResearchCsv, enrollParticipant, loadContext, loadParticipants, loadTurns, saveReview,
} from '@/lib/researchReview';
import type { ContextTurn, Disposition, Page, Participant, Period, Review, Turn } from '@/lib/researchReview';
import styles from './research.module.css';

const labels: Record<Disposition, string> = {
  pending: 'Belum ditelaah',
  study: 'Masuk penelitian',
  practice: 'Latihan antarmuka',
  test: 'Pengujian / dikeluarkan',
};
const witaDate = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Makassar' });
const witaTime = new Intl.DateTimeFormat('id-ID', {
  timeZone: 'Asia/Makassar', dateStyle: 'medium', timeStyle: 'short',
});

const showTime = (value: string) => witaTime.format(new Date(value));
const emptyPage = { data: [], next_before: null };

export default function ResearchReviewPage() {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [email, setEmail] = useState('');
  const [participantCode, setParticipantCode] = useState('');
  const [consented, setConsented] = useState(false);
  const [filter, setFilter] = useState<Period>(() => ({
    start: witaDate.format(new Date(Date.now() - 6 * 86_400_000)),
    end: witaDate.format(new Date()),
    code: '',
  }));
  const [applied, setApplied] = useState<Period | null>(null);
  const [turns, setTurns] = useState<Page<Turn>>(emptyPage);
  const [context, setContext] = useState<Page<ContextTurn>>(emptyPage);
  const [selected, setSelected] = useState<Turn | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const selectedId = selected?.id;

  useEffect(() => {
    let active = true;
    void loadParticipants()
      .then(result => { if (active) setParticipants(result.data); })
      .catch(err => { if (active) setError(String(err.message || err)); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (selectedId !== undefined) detailHeading.current?.focus();
  }, [selectedId]);

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function submitEnrollment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void perform(async () => {
      const { data } = await enrollParticipant(email.trim(), participantCode.trim().toUpperCase());
      setParticipants(current => [...current, data].sort((a, b) => a.code.localeCompare(b.code)));
      setEmail('');
      setParticipantCode('');
      setConsented(false);
      setNotice('Peserta ' + data.code + ' terdaftar. Rekaman dimulai setelah pendaftaran.');
    });
  }

  function withdraw() {
    const code = filter.code;
    if (!code || !window.confirm('Hapus pendaftaran dan semua rekaman penelaahan untuk ' + code + '?')) return;
    void perform(async () => {
      await adminFetch('/research/participants/' + code, { method: 'DELETE' });
      setParticipants(current => current.filter(participant => participant.code !== code));
      setFilter(current => ({ ...current, code: '' }));
      setApplied(null);
      setTurns(emptyPage);
      setSelected(null);
      setNotice('Rekaman penelitian peserta ' + code + ' telah dihapus dari fitur penelaahan.');
    });
  }

  function applyFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void perform(async () => {
      const page = await loadTurns(filter);
      setTurns(page);
      setApplied(filter);
      setSelected(null);
    });
  }

  function openTurn(turn: Turn) {
    void perform(async () => {
      const page = await loadContext(turn.request_id);
      setContext(page);
      setSelected(turn);
      setReview({
        disposition: turn.disposition,
        reviewed_question: turn.reviewed_question ?? '',
        reviewed_answer: turn.reviewed_answer ?? '',
      });
    });
  }

  function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !review) return;
    void perform(async () => {
      const { data } = await saveReview(selected.request_id, review);
      const updated = { ...selected, ...data };
      setTurns(current => ({
        ...current, data: current.data.map(turn => turn.id === updated.id ? updated : turn),
      }));
      setSelected(updated);
      setReview(data);
      setNotice('Status dan salinan telaah tersimpan.');
    });
  }

  function exportCsv() {
    if (!applied) return;
    void perform(async () => {
      const rows: Turn[] = [];
      let before: number | null = null;
      do {
        const page: Page<Turn> = await loadTurns(applied, before, true);
        rows.push(...page.data);
        before = page.next_before;
      } while (before !== null);
      if (rows.length === 0) {
        setNotice('Belum ada rekaman yang disetujui untuk diekspor pada filter ini.');
        return;
      }
      const href = URL.createObjectURL(new Blob([buildResearchCsv(rows.reverse())], {
        type: 'text/csv;charset=utf-8',
      }));
      const link = document.createElement('a');
      link.href = href;
      link.download = 'pertanyaan-' + applied.start + '-' + applied.end + (applied.code ? '-' + applied.code : '') + '.csv';
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(href), 1000);
      setNotice(String(rows.length) + ' pesan yang telah ditelaah diekspor.');
    });
  }

  return (
    <section className={styles.review}>
      <header>
        <h1>Penelaahan Pertanyaan Mahasiswa</h1>
        <p>Pisahkan pesan latihan dan pengujian, lalu siapkan rekaman untuk pengelompokan topik dan pemeriksaan panduan.</p>
      </header>
      {error && <p className={styles.error} role="alert">{error}</p>}
      {notice && <p className={styles.notice} role="status">{notice}</p>}

      <details className={styles.panel}>
        <summary>Daftarkan peserta yang sudah memberi persetujuan ({participants.length})</summary>
        <p>Peserta perlu login ke website satu kali. Gunakan kode peserta seperti P-001 dan simpan bukti persetujuan secara terpisah.</p>
        <form className={styles.filters} onSubmit={submitEnrollment}>
          <label>Email akun<input className="input" type="email" value={email} onChange={e => setEmail(e.target.value)} required /></label>
          <label>Kode peserta<input className="input" placeholder="P-001" maxLength={8} value={participantCode} onChange={e => setParticipantCode(e.target.value)} required /></label>
          <label className={styles.check}><input type="checkbox" checked={consented} onChange={e => setConsented(e.target.checked)} required /> Persetujuan sudah diterima</label>
          <button className="btn btn-primary" disabled={busy || !consented}>Daftarkan</button>
        </form>
      </details>

      <section className={styles.panel} aria-label="Filter rekaman">
        <form className={styles.filters} onSubmit={applyFilter}>
          <label>Mulai (WITA)<input className="input" type="date" required value={filter.start} onChange={e => setFilter({ ...filter, start: e.target.value })} /></label>
          <label>Selesai (WITA)<input className="input" type="date" required value={filter.end} onChange={e => setFilter({ ...filter, end: e.target.value })} /></label>
          <label>Peserta<select className="select" value={filter.code} onChange={e => setFilter({ ...filter, code: e.target.value })}>
            <option value="">Semua peserta terdaftar</option>
            {participants.map(participant => <option key={participant.code}>{participant.code}</option>)}
          </select></label>
          <button className="btn btn-primary" disabled={busy}>Tampilkan</button>
          {filter.code && <button type="button" className="btn btn-danger" onClick={withdraw} disabled={busy}>Tarik peserta</button>}
        </form>
        {applied && <div className={styles.bar}>
          <p>Filter aktif {applied.start} – {applied.end} · {applied.code || 'Semua peserta'} · {turns.data.length} rekaman dimuat</p>
          <button type="button" className="btn btn-outline" onClick={exportCsv} disabled={busy}>Ekspor CSV hasil telaah</button>
        </div>}
      </section>

      {applied && <section className={styles.panel} aria-label="Daftar rekaman">
        {turns.data.length === 0 ? <p>Tidak ada rekaman pada filter ini.</p> : (
          <div className={styles.scroll}>
            <table className={styles.table}>
              <thead><tr><th>Waktu (WITA)</th><th>Peserta</th><th>Pertanyaan</th><th>Status Telaah</th><th>Tindakan</th></tr></thead>
              <tbody>{turns.data.map(turn => <tr key={turn.id} aria-current={selected?.id === turn.id}>
                <td>{showTime(turn.occurred_at)}</td><td>{turn.participant_code}</td><td>{turn.question}</td>
                <td>{labels[turn.disposition]}</td>
                <td><button type="button" className="btn btn-outline-gray btn-sm" disabled={busy} onClick={() => openTurn(turn)}>Telaah</button></td>
              </tr>)}</tbody>
            </table>
          </div>
        )}
        {turns.next_before !== null && <button type="button" className="btn btn-outline-gray" disabled={busy} onClick={() => void perform(async () => {
          const page = await loadTurns(applied, turns.next_before);
          setTurns({ data: [...turns.data, ...page.data], next_before: page.next_before });
        })}>Muat rekaman berikutnya</button>}
      </section>}

      {selected && review && <section className={styles.panel} aria-label="Detail rekaman">
        <div className={styles.bar}>
          <h2 ref={detailHeading} tabIndex={-1}>Detail pertanyaan · {selected.participant_code}</h2>
          <button type="button" className="btn btn-outline-gray btn-sm" onClick={() => setSelected(null)}>Tutup detail</button>
        </div>
        <p className={styles.meta}>{showTime(selected.occurred_at)} WITA · {selected.status}{selected.http_status ? ' · HTTP ' + selected.http_status : ''}{selected.error_source ? ' · ' + selected.error_source : ''}</p>
        <p className={styles.meta}>ID pesan {selected.request_id}</p>
        <details className={styles.context}>
          <summary>Konteks sebelumnya ({context.data.length} pesan dimuat)</summary>
          {context.data.length === 0 && <p>Belum ada pesan sebelumnya yang terekam pada sesi peserta.</p>}
          {context.next_before !== null && <button type="button" className="btn btn-outline-gray btn-sm" disabled={busy} onClick={() => void perform(async () => {
            const page = await loadContext(selected.request_id, context.next_before);
            setContext({ data: [...context.data, ...page.data], next_before: page.next_before });
          })}>Muat pesan lebih lama</button>}
          {[...context.data].reverse().map(turn => <div className={styles.original} key={turn.id}>
            <p className={styles.meta}>{showTime(turn.occurred_at)} · {labels[turn.disposition]}</p>
            <p><strong>Mahasiswa</strong> {turn.question}</p>
            {turn.answer !== null && <p><strong>Chatbot</strong> {turn.answer}</p>}
          </div>)}
        </details>
        <div className={styles.original}>
          <p><strong>Pertanyaan asli</strong> {selected.question}</p>
          <p><strong>Jawaban asli</strong> {selected.answer ?? 'Tidak ada jawaban yang terekam.'}</p>
          {selected.sources.length > 0 && <ul>{selected.sources.map((source, index) => {
            const url = resolveCitationUrl(source);
            const label = (source.title || source.section || source.domain || 'Sumber') +
              (source.pages?.length ? ' · hlm. ' + source.pages.join(', ') : '');
            return <li key={index}>{url ? <a href={url} target="_blank" rel="noreferrer">{label}</a> : label}</li>;
          })}</ul>}
        </div>
        <form className={styles.reviewForm} onSubmit={submitReview}>
          <label>Status telaah<select className="select" value={review.disposition} onChange={e => setReview({ ...review, disposition: e.target.value as Disposition })}>
            {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
          {review.disposition === 'study' && <>
            <p>Periksa dan samarkan nama, NIM, email, nomor telepon, atau keterangan pribadi pada teks sebelum menyimpan salinan untuk ekspor.</p>
            <button type="button" className="btn btn-outline-gray btn-sm" onClick={() => setReview({
              ...review, reviewed_question: selected.question, reviewed_answer: selected.answer,
            })}>Salin teks asli untuk diperiksa</button>
            <label>Pertanyaan untuk ekspor<textarea className="textarea" rows={3} required maxLength={500} value={review.reviewed_question ?? ''} onChange={e => setReview({ ...review, reviewed_question: e.target.value })} /></label>
            {selected.answer !== null && <label>Jawaban untuk ekspor<textarea className="textarea" rows={5} required maxLength={30000} value={review.reviewed_answer ?? ''} onChange={e => setReview({ ...review, reviewed_answer: e.target.value })} /></label>}
          </>}
          <button className="btn btn-primary" disabled={busy}>Simpan telaah</button>
        </form>
      </section>}
    </section>
  );
}
