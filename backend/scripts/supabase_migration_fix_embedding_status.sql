-- =============================================================================
-- MIGRATION: Fix embedding_status Constraint
-- =============================================================================
-- 
-- PROBLEM: 
-- The current constraint on child_documents.embedding_status only allows:
-- ('pending', 'stale', 'success', 'failed')
-- 
-- But the code in chunk_editor.py tries to set embedding_status = 'processing'
-- which causes all re-embedding operations to fail with constraint violation.
--
-- SOLUTION:
-- Add 'processing' to the allowed values in the CHECK constraint.
--
-- DATE: September 10, 2026
-- AUTHOR: Database Schema Fix
-- =============================================================================

-- Drop the existing constraint that doesn't include 'processing'
ALTER TABLE child_documents 
DROP CONSTRAINT IF EXISTS child_documents_embedding_status_check;

-- Add the corrected constraint that includes 'processing'
ALTER TABLE child_documents 
ADD CONSTRAINT child_documents_embedding_status_check 
CHECK (embedding_status IN ('pending', 'stale', 'processing', 'success', 'failed'));

-- Verify the constraint was applied correctly
-- (This is a comment for manual verification after running the migration)
-- SELECT conname, consrc 
-- FROM pg_constraint 
-- WHERE conrelid = 'child_documents'::regclass 
--   AND conname = 'child_documents_embedding_status_check';

-- =============================================================================
-- VERIFICATION NOTES:
-- =============================================================================
-- 
-- After applying this migration:
-- 
-- 1. The re-embedding functionality in chunk_editor.py should work properly
-- 2. The trigger_reembed_chunk() function should no longer fail with constraint violations
-- 3. Admin users should be able to trigger re-embedding of chunks successfully
-- 
-- TEST CASES:
-- - Try editing a chunk's content (should set embedding_status = 'stale')
-- - Try triggering re-embedding (should set embedding_status = 'processing')
-- - Verify the embedding process completes (should set embedding_status = 'success')
-- 
-- =============================================================================