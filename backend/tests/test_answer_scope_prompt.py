from src.generation.chain import SYSTEM_PROMPT, USER_PROMPT


def test_generation_prompt_requires_scope_clarification_for_related_rules():
    prompt = f"{SYSTEM_PROMPT}\n{USER_PROMPT}".casefold()

    assert "cakupannya berbeda" in prompt
    assert "jangan menyamaratakan" in prompt
    assert "jangan hanya mengatakan informasi tidak tersedia" in prompt
    assert "riwayat percakapan hanya untuk memahami maksud" in prompt
    assert "jangan menambah syarat" in prompt
    assert "semua fakta jawaban tetap harus berasal dari dokumen" in prompt
