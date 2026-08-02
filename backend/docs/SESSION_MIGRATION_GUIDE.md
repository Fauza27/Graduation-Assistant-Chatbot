# Session Storage Migration Guide

## Overview

Migrasi dari **in-memory session storage** ke **database-backed session storage** menggunakan Supabase untuk meningkatkan persistence dan scalability.

## Perubahan Utama

### Sebelum (In-Memory)
- Session disimpan di RAM dalam dictionary Python
- Hilang saat server restart
- Tidak bisa multi-server deployment
- Memory terbatas

### Sesudah (Database-Backed)
- Session disimpan di tabel Supabase `conversation_sessions`
- Persisten across server restart
- Support multi-server deployment
- Hot LRU cache untuk performance

## Setup & Configuration

### 1. Database Migration

Jalankan SQL migration untuk membuat tabel sessions:

```bash
# Apply migration ke Supabase
psql -h your-supabase-host -U postgres -d postgres -f scripts/supabase_session_migration.sql
```

Atau copy-paste isi file `scripts/supabase_session_migration.sql` ke Supabase SQL Editor.

### 2. Environment Configuration

Update `.env` file:

```bash
# Session Management
USE_DATABASE_SESSIONS=true
TABLE_CONVERSATION_SESSIONS=conversation_sessions
MAX_ACTIVE_SESSIONS=1000
SESSION_CLEANUP_INTERVAL=3600
```

### 3. Deployment Strategy

#### Zero-Downtime Deployment

1. **Deploy kode baru** dengan `USE_DATABASE_SESSIONS=false`
2. **Test** bahwa aplikasi masih berfungsi normal
3. **Apply database migration**
4. **Enable database sessions**: Set `USE_DATABASE_SESSIONS=true`
5. **Monitor** logs dan performance
6. **Rollback** jika ada masalah: Set `USE_DATABASE_SESSIONS=false`

#### Rollback Plan

Jika ada masalah dengan database sessions:

```bash
# Immediate rollback
USE_DATABASE_SESSIONS=false

# Restart aplikasi
# Sessions akan kembali ke in-memory mode
```

## Testing

### Manual Testing

```bash
# Test basic functionality
python scripts/test_session_migration.py
```

### Integration Testing

1. **Chat continuity**: Pastikan percakapan berlanjut setelah restart
2. **Performance**: Monitor response time (target: <200ms overhead)
3. **Error handling**: Test behavior saat database down
4. **Cleanup**: Verify idle session cleanup works

## Monitoring

### Session Statistics

```python
from src.services.ai_services import get_session_stats

stats = get_session_stats()
print(f"Active sessions: {stats['total_sessions']}")
print(f"Cache hit rate: {stats['cache_size']}/{stats['total_sessions']}")
```

### Database Queries

```sql
-- Total sessions
SELECT COUNT(*) FROM conversation_sessions;

-- Active sessions (last 1 hour)
SELECT COUNT(*) FROM conversation_sessions 
WHERE last_access >= NOW() - INTERVAL '1 hour';

-- Average conversation length
SELECT AVG(jsonb_array_length(turns)) as avg_turns 
FROM conversation_sessions;

-- Cleanup idle sessions manually
SELECT cleanup_idle_sessions(3600);
```

### Logs to Monitor

```bash
# Success indicators
"Using database-backed session storage"
"Session {session_id} loaded from cache"
"Session {session_id} saved with {n} turns"

# Warning indicators  
"Failed to load session {session_id} from database"
"Falling back to in-memory session storage"

# Error indicators
"Failed to initialize database session store"
"Session save failed"
```

## Performance Characteristics

### Latency Impact

| Operation | In-Memory | Database (Cache Hit) | Database (Cache Miss) |
|-----------|-----------|---------------------|----------------------|
| Load session | ~0ms | ~0ms | ~50-100ms |
| Save session | ~0ms | ~50-100ms | ~50-100ms |
| First chat | ~0ms | ~50-100ms | ~50-100ms |
| Subsequent chats | ~0ms | ~0ms | ~0ms |

### Memory Usage

| Mode | Memory per Session | Max Sessions | Total Memory |
|------|-------------------|--------------|--------------|
| In-Memory | ~50KB | 1000 | ~50MB |
| Database + Cache | ~50KB | 50 (cache) | ~2.5MB |

## Troubleshooting

### Common Issues

#### 1. Database Connection Failed

```
Error: Failed to initialize database session store
```

**Solutions:**
- Check `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`
- Verify Supabase project is active
- Check network connectivity
- Fallback: Set `USE_DATABASE_SESSIONS=false`

#### 2. Migration Table Missing

```
Error: relation "conversation_sessions" does not exist
```

**Solutions:**
- Run database migration: `scripts/supabase_session_migration.sql`
- Check table name in `TABLE_CONVERSATION_SESSIONS` setting
- Verify RLS policies allow service role access

#### 3. High Latency

```
Warning: Session operations taking >200ms
```

**Solutions:**
- Check Supabase region (use closest to your server)
- Monitor cache hit rate (should be >90% for active users)
- Consider increasing `MAX_ACTIVE_SESSIONS` for larger cache
- Check database connection pooling

#### 4. Session Data Corruption

```
Error: Failed to deserialize session data
```

**Solutions:**
- Check `ConversationMemory.from_dict()` compatibility
- Clear corrupted session: `DELETE FROM conversation_sessions WHERE session_id = 'xxx'`
- Monitor for schema changes in Turn/ConversationMemory classes

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger("src.services.session_store").setLevel(logging.DEBUG)
```

## Migration Checklist

- [ ] Database migration applied
- [ ] Environment variables updated
- [ ] Test script passes
- [ ] Backup plan ready
- [ ] Monitoring setup
- [ ] Performance baseline established
- [ ] Team notified of deployment
- [ ] Rollback procedure tested

## Future Improvements

1. **Write-behind caching**: Batch saves every 30s for better performance
2. **Session compression**: Compress large conversation histories
3. **Distributed cache**: Redis layer for multi-region deployments
4. **Analytics**: Session duration, conversation patterns, user behavior
5. **Archival**: Move old sessions to cold storage