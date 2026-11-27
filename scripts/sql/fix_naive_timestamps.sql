-- Corrects the rows that check_naive_timestamps.sql reports as 'shifted' (see there for how a
-- row is judged). Rows reported as 'review' are left alone. updated_at is not changed.
--
-- DRY RUN BY DEFAULT: it prints what it would change and rolls back.
-- It commits only when run with exactly:  psql -v apply=1
--
-- Run it after the fixed code is deployed, and after a backup. Running it twice is harmless.
-- 'America/Chicago' is the apex server's timezone.

\set ON_ERROR_STOP on
BEGIN;

WITH converted AS (
    SELECT id, deleted_at AS old_value, updated_at AS reference,
           (deleted_at AT TIME ZONE 'America/Chicago') AT TIME ZONE 'UTC' AS corrected
      FROM projects
     WHERE deleted_at - updated_at > interval '60 seconds'
       AND abs(extract(epoch FROM deleted_at - updated_at) - 3600) > 60
       FOR UPDATE
), candidates AS (
    SELECT *,
           CASE WHEN ((corrected - interval '1 hour') AT TIME ZONE 'UTC')
                     AT TIME ZONE 'America/Chicago' = old_value
                THEN corrected - interval '1 hour' END AS earlier
      FROM converted
), target AS (
    SELECT id, old_value,
           CASE WHEN abs(extract(epoch FROM earlier - reference)) <= 60 THEN earlier
                ELSE corrected END AS new_value
      FROM candidates
     WHERE (earlier IS NULL AND corrected - reference <= interval '60 seconds')
        OR abs(extract(epoch FROM corrected - reference)) <= 60
        OR abs(extract(epoch FROM earlier - reference)) <= 60
)
UPDATE projects AS row_to_fix SET deleted_at = target.new_value
  FROM target WHERE row_to_fix.id = target.id
RETURNING 'projects.deleted_at' AS column_name, row_to_fix.id, target.old_value,
          row_to_fix.deleted_at AS new_value;

WITH converted AS (
    SELECT id, completed_at AS old_value, updated_at AS reference,
           (completed_at AT TIME ZONE 'America/Chicago') AT TIME ZONE 'UTC' AS corrected
      FROM tasks
     WHERE completed_at - updated_at > interval '60 seconds'
       AND abs(extract(epoch FROM completed_at - updated_at) - 3600) > 60
       FOR UPDATE
), candidates AS (
    SELECT *,
           CASE WHEN ((corrected - interval '1 hour') AT TIME ZONE 'UTC')
                     AT TIME ZONE 'America/Chicago' = old_value
                THEN corrected - interval '1 hour' END AS earlier
      FROM converted
), target AS (
    SELECT id, old_value,
           CASE WHEN abs(extract(epoch FROM earlier - reference)) <= 60 THEN earlier
                ELSE corrected END AS new_value
      FROM candidates
     WHERE (earlier IS NULL AND corrected - reference <= interval '60 seconds')
        OR abs(extract(epoch FROM corrected - reference)) <= 60
        OR abs(extract(epoch FROM earlier - reference)) <= 60
)
UPDATE tasks AS row_to_fix SET completed_at = target.new_value
  FROM target WHERE row_to_fix.id = target.id
RETURNING 'tasks.completed_at' AS column_name, row_to_fix.id, target.old_value,
          row_to_fix.completed_at AS new_value;

WITH converted AS (
    SELECT id, last_db_write AS old_value, updated_at AS reference,
           (last_db_write AT TIME ZONE 'America/Chicago') AT TIME ZONE 'UTC' AS corrected
      FROM doc_sync_states
     WHERE last_db_write - updated_at > interval '60 seconds'
       AND abs(extract(epoch FROM last_db_write - updated_at) - 3600) > 60
       FOR UPDATE
), candidates AS (
    SELECT *,
           CASE WHEN ((corrected - interval '1 hour') AT TIME ZONE 'UTC')
                     AT TIME ZONE 'America/Chicago' = old_value
                THEN corrected - interval '1 hour' END AS earlier
      FROM converted
), target AS (
    SELECT id, old_value,
           CASE WHEN abs(extract(epoch FROM earlier - reference)) <= 60 THEN earlier
                ELSE corrected END AS new_value
      FROM candidates
     WHERE (earlier IS NULL AND corrected - reference <= interval '60 seconds')
        OR abs(extract(epoch FROM corrected - reference)) <= 60
        OR abs(extract(epoch FROM earlier - reference)) <= 60
)
UPDATE doc_sync_states AS row_to_fix SET last_db_write = target.new_value
  FROM target WHERE row_to_fix.id = target.id
RETURNING 'doc_sync_states.last_db_write' AS column_name, row_to_fix.id, target.old_value,
          row_to_fix.last_db_write AS new_value;

\if :{?apply}
\else
    \set apply 0
\endif
SELECT :'apply' = '1' AS commit_requested \gset

\if :commit_requested
    COMMIT;
    \echo 'Committed.'
\else
    ROLLBACK;
    \echo 'Dry run: rolled back, nothing changed. Use -v apply=1 to commit.'
\endif
