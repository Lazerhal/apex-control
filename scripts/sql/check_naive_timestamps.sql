-- READ ONLY. Changes nothing.
--
-- Until the timezone fix, the API wrote datetime.utcnow() without a timezone, and it was stored
-- as local time: later than the truth by the server's UTC offset (5 or 6 hours in Central).
-- The offset that applied is the one for the value's own wall-clock time, so the corrected value
-- is the stored one read back as Central wall-clock time and taken as UTC.
--
-- Each of these writes also set updated_at from the database clock, which was right, so:
--   ok       the value matches updated_at
--   shifted  the value is later than updated_at, and the corrected value is not
--   review   cannot be told from the data (for example a task edited after it was completed)
--
-- When clocks spring forward, two different times were stored as the same value. Those rows are
-- 'shifted' only if updated_at shows which one it was, and 'review' otherwise.
-- A value exactly one hour after updated_at is also 'review': an earlier version of the
-- correction script could leave that behind, and correcting it again would be wrong.
--
-- 'America/Chicago' is the apex server's timezone. Run with psql.

\set ON_ERROR_STOP on
BEGIN TRANSACTION READ ONLY;

-- 1. Timestamps: how many of each verdict, then every row that is not ok
WITH written AS (
    SELECT 'projects.deleted_at' AS column_name, id, deleted_at AS value, updated_at AS reference
      FROM projects WHERE deleted_at IS NOT NULL
    UNION ALL
    SELECT 'tasks.completed_at', id, completed_at, updated_at
      FROM tasks WHERE completed_at IS NOT NULL
    UNION ALL
    SELECT 'doc_sync_states.last_db_write', id, last_db_write, updated_at
      FROM doc_sync_states WHERE last_db_write IS NOT NULL
), converted AS (
    SELECT *,
           value - reference AS difference,
           (value AT TIME ZONE 'America/Chicago') AT TIME ZONE 'UTC' AS corrected
      FROM written
), candidates AS (
    -- earlier: the other possible answer, in the hour that clocks skip in spring
    SELECT *,
           CASE WHEN ((corrected - interval '1 hour') AT TIME ZONE 'UTC')
                     AT TIME ZONE 'America/Chicago' = value
                THEN corrected - interval '1 hour' END AS earlier
      FROM converted
), judged AS (
    SELECT *,
           CASE WHEN abs(extract(epoch FROM difference)) <= 60 THEN 'ok'
                WHEN difference <= interval '60 seconds'
                  OR abs(extract(epoch FROM difference) - 3600) <= 60 THEN 'review'
                WHEN earlier IS NULL AND corrected - reference <= interval '60 seconds'
                     THEN 'shifted'
                WHEN abs(extract(epoch FROM corrected - reference)) <= 60
                  OR abs(extract(epoch FROM earlier - reference)) <= 60 THEN 'shifted'
                ELSE 'review' END AS verdict
      FROM candidates
)
SELECT column_name, verdict, count(*) AS row_count
  FROM judged
 GROUP BY column_name, verdict
 ORDER BY column_name, verdict;

WITH written AS (
    SELECT 'projects.deleted_at' AS column_name, id, deleted_at AS value, updated_at AS reference
      FROM projects WHERE deleted_at IS NOT NULL
    UNION ALL
    SELECT 'tasks.completed_at', id, completed_at, updated_at
      FROM tasks WHERE completed_at IS NOT NULL
    UNION ALL
    SELECT 'doc_sync_states.last_db_write', id, last_db_write, updated_at
      FROM doc_sync_states WHERE last_db_write IS NOT NULL
), converted AS (
    SELECT *,
           value - reference AS difference,
           (value AT TIME ZONE 'America/Chicago') AT TIME ZONE 'UTC' AS corrected
      FROM written
), candidates AS (
    -- earlier: the other possible answer, in the hour that clocks skip in spring
    SELECT *,
           CASE WHEN ((corrected - interval '1 hour') AT TIME ZONE 'UTC')
                     AT TIME ZONE 'America/Chicago' = value
                THEN corrected - interval '1 hour' END AS earlier
      FROM converted
), judged AS (
    SELECT *,
           CASE WHEN abs(extract(epoch FROM difference)) <= 60 THEN 'ok'
                WHEN difference <= interval '60 seconds'
                  OR abs(extract(epoch FROM difference) - 3600) <= 60 THEN 'review'
                WHEN earlier IS NULL AND corrected - reference <= interval '60 seconds'
                     THEN 'shifted'
                WHEN abs(extract(epoch FROM corrected - reference)) <= 60
                  OR abs(extract(epoch FROM earlier - reference)) <= 60 THEN 'shifted'
                ELSE 'review' END AS verdict
      FROM candidates
)
SELECT column_name, id, value, reference AS updated_at, difference, verdict
  FROM judged
 WHERE verdict <> 'ok'
 ORDER BY column_name, value;

-- 2. Left over from other bugs fixed at the same time (the correction script does not touch these)
SELECT 'completed_at on a task that is not done' AS problem, id, status, completed_at
  FROM tasks WHERE completed_at IS NOT NULL AND status IS DISTINCT FROM 'done';

SELECT 'duplicate apex_task_id' AS problem, project_id, apex_task_id, count(*) AS row_count
  FROM tasks GROUP BY project_id, apex_task_id HAVING count(*) > 1;

SELECT 'missing or NaN amount' AS problem, id, name, monthly_cost_usd, monthly_revenue_usd,
       cost_efficiency_flag
  FROM projects
 WHERE monthly_cost_usd IS NULL OR monthly_revenue_usd IS NULL OR cost_efficiency_flag IS NULL
    OR monthly_cost_usd = 'NaN' OR monthly_revenue_usd = 'NaN';

ROLLBACK;
