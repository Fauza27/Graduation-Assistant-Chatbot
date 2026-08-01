import json

data = json.load(open('evaluation_results_no_gt_20260501_145309.json', encoding='utf-8'))
details = data['details']

# Sort by answer_relevancy
low_ar = sorted(details, key=lambda x: x['metrics']['answer_relevancy'] if x['metrics']['answer_relevancy'] is not None else 0)

print("=" * 120)
print("TOP 25 LOWEST ANSWER RELEVANCY SCORES")
print("=" * 120)

for i, d in enumerate(low_ar[:25], 1):
    ar = d['metrics']['answer_relevancy']
    faith = d['metrics']['faithfulness']
    q = d['question']
    a = d['answer']
    is_td = "tidak ditemukan" in a.lower()
    word_count = len(a.split())
    
    print(f"\n--- [{i}] AR={ar:.4f} | Faith={faith:.4f} | Words={word_count} | TidakDitemukan={is_td}")
    print(f"  Q: {q}")
    print(f"  A: {a[:200]}")

print("\n" + "=" * 120)
print("ANSWER LENGTH STATS")
print("=" * 120)

# Stats
ar_scores = [d['metrics']['answer_relevancy'] for d in details if d['metrics']['answer_relevancy'] is not None]
word_counts = [len(d['answer'].split()) for d in details]
td_count = sum(1 for d in details if "tidak ditemukan" in d['answer'].lower())

print(f"Total questions: {len(details)}")
print(f"Tidak ditemukan: {td_count}")
print(f"Mean AR: {sum(ar_scores)/len(ar_scores):.4f}")
print(f"Mean word count: {sum(word_counts)/len(word_counts):.1f}")
print(f"Min word count: {min(word_counts)}")
print(f"Max word count: {max(word_counts)}")

# Correlation: word count vs AR
print("\n" + "=" * 120)
print("WORD COUNT vs AR (binned)")
print("=" * 120)
bins = [(0, 10), (10, 20), (20, 30), (30, 50), (50, 100), (100, 500)]
for lo, hi in bins:
    items = [(d['metrics']['answer_relevancy'], len(d['answer'].split())) for d in details 
             if d['metrics']['answer_relevancy'] is not None and lo <= len(d['answer'].split()) < hi]
    if items:
        avg_ar = sum(x[0] for x in items) / len(items)
        print(f"  {lo}-{hi} words: {len(items)} answers, avg AR={avg_ar:.4f}")

# Check for preamble patterns
print("\n" + "=" * 120)
print("PREAMBLE PATTERNS")
print("=" * 120)
preamble_patterns = [
    "adalah sebagai berikut",
    "berdasarkan",
    "dalam dokumen",
    "sesuai dengan",
    "menurut",
    "Format penulisan",
    "BAB ",
]
for pat in preamble_patterns:
    count = sum(1 for d in details if pat.lower() in d['answer'].lower())
    if count > 0:
        # Get avg AR for those with pattern
        items_with = [d['metrics']['answer_relevancy'] for d in details 
                      if pat.lower() in d['answer'].lower() and d['metrics']['answer_relevancy'] is not None]
        items_without = [d['metrics']['answer_relevancy'] for d in details 
                         if pat.lower() not in d['answer'].lower() and d['metrics']['answer_relevancy'] is not None]
        avg_with = sum(items_with)/len(items_with) if items_with else 0
        avg_without = sum(items_without)/len(items_without) if items_without else 0
        print(f"  '{pat}': {count} answers, avg AR={avg_with:.4f} vs without={avg_without:.4f}")
