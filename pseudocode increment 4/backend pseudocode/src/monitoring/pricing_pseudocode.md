# Pseudocode untuk `src/monitoring/pricing.py`

```markdown
ALGORITMA KALKULASI BIAYA OPENAI (pricing.py)

Menghitung biaya (cost) request ke OpenAI berdasarkan token usage,
menggunakan harga yang dikonfigurasi di config/pricing.yaml.

1. INISIALISASI MODULE
   - Tentukan path ke file pricing.yaml (relatif terhadap root project).
   - FUNGSI _load_pricing(path):
     - JIKA file tidak ada: log error, kembalikan dict kosong {"llm": {}, "embedding": {}}.
     - Baca dan parse YAML.
     - Kembalikan dict harga.
   - Load pricing saat module di-import (cache di module level), pola sama dengan
     section_keywords.yaml di self_query.py.

2. STRUKTUR config/pricing.yaml:
   ```yaml
   llm:
     gpt-4o-mini:
       input_per_1m: 0.15    # USD per 1 juta input token
       output_per_1m: 0.60   # USD per 1 juta output token
     gpt-4o:
       input_per_1m: 2.50
       output_per_1m: 10.00
   embedding:
     text-embedding-3-large:
       input_per_1m: 0.13
     text-embedding-3-small:
       input_per_1m: 0.02
   ```

3. FUNGSI calculate_llm_cost(model, input_tokens, output_tokens) -> float
   - Ambil pricing untuk model dari _PRICING["llm"][model].
   - JIKA model tidak ada di config ATAU tokens None:
     - Log warning model tidak ditemukan.
     - Kembalikan 0.0.
   - Hitung cost:
     - input_cost = input_tokens / 1_000_000 * input_per_1m
     - output_cost = output_tokens / 1_000_000 * output_per_1m
     - total = input_cost + output_cost
   - Kembalikan round(total, 6).

4. FUNGSI calculate_embedding_cost(model, tokens) -> float
   - Ambil pricing untuk model dari _PRICING["embedding"][model].
   - JIKA model tidak ada ATAU tokens None:
     - Log warning model tidak ditemukan.
     - Kembalikan 0.0.
   - Hitung cost = tokens / 1_000_000 * input_per_1m.
   - Kembalikan round(cost, 6).

CATATAN PENTING:
   - Harga dapat berubah sewaktu-waktu — update config/pricing.yaml sebelum
     digunakan untuk keputusan bisnis.
   - File YAML ini mudah diupdate tanpa mengubah kode Python.
```
