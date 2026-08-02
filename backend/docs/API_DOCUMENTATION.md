# API Documentation

## Overview

RAG Chatbot API untuk panduan akademik KKP/PI STMIK Widya Cipta Dharma.

**Base URL**: `http://localhost:8000` (development) atau URL production Anda

## Authentication

Saat ini API tidak memerlukan authentication untuk endpoint publik. Rate limiting diterapkan per IP address.

## Rate Limiting

- **Limit**: 13 requests per day per user/IP
- **Window**: 24 jam (86400 detik)
- **Headers**: Response akan menyertakan header `X-RateLimit-*` untuk monitoring

## Endpoints

### Health Check

#### GET `/health/`

Basic health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-05-13T10:30:00Z",
  "version": "1.0.0",
  "environment": "production",
  "uptime_seconds": 3600.5
}
```

#### GET `/health/detailed`

Detailed health check dengan status semua services.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-05-13T10:30:00Z",
  "version": "1.0.0",
  "environment": "production",
  "uptime_seconds": 3600.5,
  "services": {
    "openai": {
      "status": "healthy",
      "response_time_ms": 245.67,
      "model_count": 15
    },
    "supabase": {
      "status": "healthy", 
      "response_time_ms": 89.23,
      "document_count": 1250
    },
    "telegram_bot": {
      "status": "configured"
    }
  },
  "system": {
    "python_version": "3.9+",
    "max_concurrent_requests": 10,
    "rate_limit_per_day": 13
  },
  "sessions": {
    "active_sessions": 5,
    "total_turns": 23,
    "sessions": ["user1", "user2", "user3"]
  }
}
```

### Chat API

#### POST `/api/chat`

Kirim pertanyaan ke chatbot.

**Request Body**:
```json
{
  "question": "Apa syarat SKS minimal untuk mengambil PI?",
  "session_id": "user123"
}
```

**Parameters**:
- `question` (string, required): Pertanyaan pengguna
- `session_id` (string, required): Unique identifier untuk session

**Response Success**:
```json
{
  "answer": "Berdasarkan BAB II Ketentuan Umum Buku Panduan PI, syarat SKS minimal untuk mengambil Penulisan Ilmiah (PI) adalah 120 SKS dengan IP Kumulatif minimal 2.00.",
  "num_docs": 3,
  "intent": "needs_retrieval",
  "confidence": 0.95,
  "search_performed": true,
  "results_found": true,
  "sources": [
    {
      "section": "BAB II",
      "title": "Ketentuan Umum PI",
      "parent_id": "pi_doc_001",
      "score": 0.89
    }
  ]
}
```

**Response Error**:
```json
{
  "answer": "Maaf, terjadi kesalahan saat memproses pertanyaan Anda.",
  "num_docs": 0,
  "error": "Retrieval failed: Database connection timeout",
  "error_type": "RetrievalError"
}
```

**Status Codes**:
- `200`: Success
- `400`: Bad request (missing parameters)
- `429`: Rate limit exceeded
- `500`: Internal server error

### Session Management

#### DELETE `/api/sessions/{session_id}`

Clear conversation history untuk session tertentu.

**Parameters**:
- `session_id` (string, path): Session ID yang akan dihapus

**Response**:
```json
{
  "success": true,
  "message": "Session cleared successfully"
}
```

#### GET `/api/sessions/stats`

Get statistik semua active sessions (admin only).

**Response**:
```json
{
  "active_sessions": 10,
  "total_turns": 156,
  "sessions": ["user1", "user2", "..."]
}
```

### Telegram Webhook

#### POST `/api/telegram/webhook`

Endpoint untuk menerima updates dari Telegram Bot API.

**Note**: Endpoint ini hanya digunakan oleh Telegram servers. Tidak untuk penggunaan manual.

## Error Handling

API menggunakan standard HTTP status codes dan mengembalikan error dalam format JSON:

```json
{
  "detail": "Error message",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2026-05-13T10:30:00Z"
}
```

### Common Error Codes

- `RATE_LIMIT_EXCEEDED`: Terlalu banyak requests
- `INVALID_SESSION_ID`: Session ID tidak valid
- `EMPTY_QUESTION`: Pertanyaan kosong
- `RETRIEVAL_ERROR`: Error dalam proses pencarian dokumen
- `GENERATION_ERROR`: Error dalam proses generate jawaban
- `SERVICE_UNAVAILABLE`: Service dependency tidak tersedia

## Rate Limiting Headers

Setiap response menyertakan header untuk monitoring rate limit:

```
X-RateLimit-Limit: 13
X-RateLimit-Remaining: 8
X-RateLimit-Reset: 1684567890
X-RateLimit-Window: 86400
```

## SDK Examples

### Python

```python
import requests

def ask_question(question: str, session_id: str) -> dict:
    response = requests.post(
        "http://localhost:8000/api/chat",
        json={
            "question": question,
            "session_id": session_id
        }
    )
    return response.json()

# Usage
result = ask_question("Apa syarat PI?", "user123")
print(result["answer"])
```

### JavaScript

```javascript
async function askQuestion(question, sessionId) {
    const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            question: question,
            session_id: sessionId
        })
    });
    
    return await response.json();
}

// Usage
const result = await askQuestion("Apa syarat PI?", "user123");
console.log(result.answer);
```

### cURL

```bash
curl -X POST "http://localhost:8000/api/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "Apa syarat SKS minimal untuk PI?",
       "session_id": "user123"
     }'
```

## Monitoring & Observability

### Metrics Endpoints

- `/health/` - Basic health check
- `/health/detailed` - Detailed system status
- `/health/readiness` - Kubernetes readiness probe
- `/health/liveness` - Kubernetes liveness probe

### Logging

Aplikasi menggunakan structured logging dengan level:
- `DEBUG`: Detailed debugging information
- `INFO`: General information
- `WARNING`: Warning messages
- `ERROR`: Error messages

Log format:
```
2026-05-13 10:30:00 | INFO | [session=user123] Question: Apa syarat PI?
2026-05-13 10:30:01 | INFO | [session=user123] Intent: needs_retrieval (conf=0.95)
2026-05-13 10:30:02 | DEBUG | [session=user123] Found 5 search results
```

## Deployment

### Environment Variables

Required:
- `OPEN_API_KEY`: OpenAI API key
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_KEY`: Supabase service key
- `TELEGRAM_BOT_TOKEN`: Telegram bot token

Optional:
- `ENVIRONMENT`: development/staging/production
- `DEBUG`: Enable debug mode
- `RATE_LIMIT_REQUESTS`: Requests per day (default: 13)
- `MAX_CONCURRENT_REQUESTS`: Max concurrent requests (default: 10)

### Docker

```bash
# Build
docker build -t rag-chatbot .

# Run
docker run -p 8000:8000 --env-file .env rag-chatbot
```

### Docker Compose

```bash
# Production
docker-compose up -d

# Development
docker-compose --profile dev up
```