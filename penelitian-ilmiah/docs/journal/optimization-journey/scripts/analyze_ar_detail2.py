import json

data = json.load(open('evaluation_results_no_gt_20260501_145309.json', encoding='utf-8'))
details = data['details']

# HIGH AR answers - what do they look like?
high_ar = sorted(details, key=lambda x: x['metrics']['answer_relevancy'] if x['metrics']['answer_relevancy'] is not None else 0, reverse=True)

print("=" * 120)
print("TOP 15 HIGHEST ANSWER RELEVANCY SCORES - WHAT WORKS")
print("=" * 120)

for i, d in enumerate(high_ar[:15], 1):
    ar = d['metrics']['answer_relevancy']
    q = d['question']
    a = d['answer']
    word_count = len(a.split())
    print(f"\n--- [{i}] AR={ar:.4f} | Words={word_count}")
    print(f"  Q: {q}")
    print(f"  A: {a[:200]}")

# Key patterns in HIGH vs LOW AR
print("\n\n" + "=" * 120)
print("PATTERN ANALYSIS: What makes AR high vs low?")
print("=" * 120)

# 1. Answers that START with question keywords
# 2. Answers that use PARAGRAPH vs LIST format
# 3. Answers that contain the question's key term

for d in details:
    ar = d['metrics']['answer_relevancy']
    q = d['question'].lower()
    a = d['answer']
    
    # Check: does answer start with a list marker?
    starts_list = a.strip().startswith('-') or a.strip().startswith('1.')
    # Check: does answer contain "BAB"
    has_bab = 'BAB ' in a
    # Check: does answer re-state question
    
    d['_starts_list'] = starts_list
    d['_has_bab'] = has_bab
    d['_word_count'] = len(a.split())

# Stats
list_items = [d for d in details if d['_starts_list'] and d['metrics']['answer_relevancy'] is not None]
para_items = [d for d in details if not d['_starts_list'] and d['metrics']['answer_relevancy'] is not None]

if list_items:
    avg_list = sum(d['metrics']['answer_relevancy'] for d in list_items) / len(list_items)
    print(f"\nList-format answers: {len(list_items)}, avg AR={avg_list:.4f}")
if para_items:
    avg_para = sum(d['metrics']['answer_relevancy'] for d in para_items) / len(para_items)
    print(f"Paragraph-format answers: {len(para_items)}, avg AR={avg_para:.4f}")

# Reference format answers (the ones about daftar pustaka)
ref_items = [d for d in details if 'referensi' in d['question'].lower() or 'daftar pustaka' in d['question'].lower()]
print(f"\nReference-format questions: {len(ref_items)}")
for d in ref_items:
    ar = d['metrics']['answer_relevancy']
    print(f"  AR={ar:.4f} | Q: {d['question'][:60]} | A: {d['answer'][:80]}")

# BAB answers
bab_items = [d for d in details if d['_has_bab'] and d['metrics']['answer_relevancy'] is not None]
if bab_items:
    avg_bab = sum(d['metrics']['answer_relevancy'] for d in bab_items) / len(bab_items)
    non_bab = [d for d in details if not d['_has_bab'] and d['metrics']['answer_relevancy'] is not None]
    avg_non_bab = sum(d['metrics']['answer_relevancy'] for d in non_bab) / len(non_bab)
    print(f"\nAnswers with 'BAB': {len(bab_items)}, avg AR={avg_bab:.4f}")
    print(f"Answers without 'BAB': {len(non_bab)}, avg AR={avg_non_bab:.4f}")

# Question type analysis
print("\n" + "=" * 120)
print("QUESTION TYPE ANALYSIS")
print("=" * 120)

q_types = {
    "Berapa": [],
    "Apa syarat": [],
    "Apa saja": [],
    "Apa isi": [],
    "Apa yang": [],
    "Bagaimana": [],
    "Siapa": [],
    "Dalam kondisi": [],
}

for d in details:
    if d['metrics']['answer_relevancy'] is None:
        continue
    for qtype in q_types:
        if d['question'].startswith(qtype):
            q_types[qtype].append(d['metrics']['answer_relevancy'])
            break

for qtype, scores in sorted(q_types.items(), key=lambda x: sum(x[1])/len(x[1]) if x[1] else 0):
    if scores:
        avg = sum(scores) / len(scores)
        print(f"  '{qtype}...': {len(scores)} questions, avg AR={avg:.4f}")
