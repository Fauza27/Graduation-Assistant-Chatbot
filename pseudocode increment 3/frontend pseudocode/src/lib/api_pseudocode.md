ALGORITMA PEMANGGILAN API

1. FUNGSI sendChatMessage(query, session_id)
   - Ambil token lewat `getAuthToken()`.
   - JIKA tidak ada token, paksa logout.
   - PANGGIL POST `NEXT_PUBLIC_API_BASE_URL/api/ai/chat` ke backend.
   - Set Header:
     - `Content-Type: application/json`
     - `Authorization: Bearer <token>`
   - Set Body:
     - `query`: teks dari user
     - `session_id`: ID unik percakapan
     - `channel`: "website"
   - KEMBALIKAN data jawaban JSON dari backend.
   - JIKA error HTTP 401: Token kedaluwarsa, paksa logout.
   - JIKA error HTTP 429: Kembalikan pesan limit harian habis.
