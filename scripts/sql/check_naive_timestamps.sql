-- READ ONLY. Changes nothing.
--
-- Until the timezone fix, the API wrote datetime.utcnow() without a timezone, and it was stored
-- as local time: later than the truth by the server's UTC offset (5 or 6 hours in Central).
--
-- Each of these writes also set updated_at from the database clock, which was right, so:
--   ok       the value matches updated_at
--   shifted  the value is later than updated_at by no more than the offset (impossible if right)
--   review   cannot be told from the data (for example a task edited after it was completed)
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
), judged AS (
    SELECT *,
           value - reference AS difference,
           (reference AT TIME ZONE 'UTC') - (reference AT TIME ZONE 'America/Chicago') AS utc_offset
      FROM written
)
SELECT column_name, verdict, count(*) AS row_count
  FROM (SELECT column_name,
               CASE WHEN abs(extract(epoch FROM difference)) <= 60 THEN 'ok'
                    WHEN difference > interval '60 seconds'
                     AND difference <= utc_offset + interval '60 seconds' THEN 'shifted'
                    ELSE 'review' END AS verdict
          FROM judged) AS verdicts
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
), judged AS (
    SELECT *,
           value - reference AS difference,
           (reference AT TIME ZONE 'UTC') - (reference AT TIME ZONE 'America/Chicago') AS utc_offset
      FROM written
)
SELECT column_name, id, value, reference AS updated_at, difference,
       CASE WHEN difference > interval '60 seconds'
             AND difference <= utc_offset + interval '60 seconds' THEN 'shifted'
            ELSE 'review' END AS verdict
  FROM judged
 WHERE abs(extract(epoch FROM difference)) > 60
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
