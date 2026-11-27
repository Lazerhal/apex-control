-- Corrects the rows that check_naive_timestamps.sql reports as 'shifted' by subtracting the
-- server's UTC offset. Rows reported as 'review' are left alone. updated_at is not changed.
--
-- DRY RUN BY DEFAULT: it prints what it would change and rolls back.
-- To commit, run psql with:  -v apply=1
--
-- Run it after the fixed code is deployed, and after a backup. Running it twice is harmless.
-- 'America/Chicago' is the apex server's timezone.

\set ON_ERROR_STOP on
BEGIN;

WITH target AS (
    SELECT id, deleted_at AS old_value,
           (updated_at AT TIME ZONE 'UTC') - (updated_at AT TIME ZONE 'America/Chicago') AS utc_offset
      FROM projects
     WHERE deleted_at - updated_at > interval '60 seconds'
       AND deleted_at - updated_at <= (updated_at AT TIME ZONE 'UTC')
           - (updated_at AT TIME ZONE 'America/Chicago') + interval '60 seconds'
       FOR UPDATE
)
UPDATE projects AS row_to_fix SET deleted_at = target.old_value - target.utc_offset
  FROM target WHERE row_to_fix.id = target.id
RETURNING 'projects.deleted_at' AS column_name, row_to_fix.id, target.old_value,
          row_to_fix.deleted_at AS new_value;

WITH target AS (
    SELECT id, completed_at AS old_value,
           (updated_at AT TIME ZONE 'UTC') - (updated_at AT TIME ZONE 'America/Chicago') AS utc_offset
      FROM tasks
     WHERE completed_at - updated_at > interval '60 seconds'
       AND completed_at - updated_at <= (updated_at AT TIME ZONE 'UTC')
           - (updated_at AT TIME ZONE 'America/Chicago') + interval '60 seconds'
       FOR UPDATE
)
UPDATE tasks AS row_to_fix SET completed_at = target.old_value - target.utc_offset
  FROM target WHERE row_to_fix.id = target.id
RETURNING 'tasks.completed_at' AS column_name, row_to_fix.id, target.old_value,
          row_to_fix.completed_at AS new_value;

WITH target AS (
    SELECT id, last_db_write AS old_value,
           (updated_at AT TIME ZONE 'UTC') - (updated_at AT TIME ZONE 'America/Chicago') AS utc_offset
      FROM doc_sync_states
     WHERE last_db_write - updated_at > interval '60 seconds'
       AND last_db_write - updated_at <= (updated_at AT TIME ZONE 'UTC')
           - (updated_at AT TIME ZONE 'America/Chicago') + interval '60 seconds'
       FOR UPDATE
)
UPDATE doc_sync_states AS row_to_fix SET last_db_write = target.old_value - target.utc_offset
  FROM target WHERE row_to_fix.id = target.id
RETURNING 'doc_sync_states.last_db_write' AS column_name, row_to_fix.id, target.old_value,
          row_to_fix.last_db_write AS new_value;

\if :{?apply}
    COMMIT;
    \echo 'Committed.'
\else
    ROLLBACK;
    \echo 'Dry run: rolled back, nothing changed. Add -v apply=1 to commit.'
\endif
