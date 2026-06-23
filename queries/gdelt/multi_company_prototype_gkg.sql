-- ARCHIVED REFERENCE ONLY.
--
-- This BigQuery template is not part of the selected zero-cost implementation
-- route because the current project should not require Google Cloud,
-- BigQuery, billing setup, or cloud credentials. Keep it only as a reference
-- for the technically feasible but rejected BigQuery path.
--
-- GDELT GKG multi-company prototype query template.
-- Placeholder variables rendered by scripts/probe_gdelt_metadata.py:
--   start_date
--   end_date
--   company_alias_rows
--   max_rows
--
-- company_alias_rows should render rows with:
--   ticker
--   company_alias
--
-- This template returns metadata only. Do not store article text.

DECLARE start_date DATE DEFAULT DATE(${start_date_literal});
DECLARE end_date DATE DEFAULT DATE(${end_date_literal});
DECLARE max_rows INT64 DEFAULT ${max_rows};

WITH company_aliases AS (
  ${company_alias_rows}
)
SELECT
  g.DocumentIdentifier AS document_identifier,
  g.SourceCommonName AS source,
  PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(g.DATE AS STRING)) AS timestamp,
  g.SourceCollectionIdentifier AS source_collection_identifier,
  a.company_alias AS matched_company_alias,
  a.ticker AS matched_ticker,
  FORMAT_DATE('%Y-%m-%d', start_date) AS query_start_date,
  FORMAT_DATE('%Y-%m-%d', end_date) AS query_end_date,
  'gdelt_gkg_multi_company_template' AS query_method
FROM `gdelt-bq.gdeltv2.gkg_partitioned` AS g
JOIN company_aliases AS a
  ON (
    STRPOS(LOWER(IFNULL(g.V2Organizations, '')), LOWER(a.company_alias)) > 0
    OR STRPOS(LOWER(IFNULL(g.DocumentIdentifier, '')), LOWER(a.company_alias)) > 0
  )
WHERE g._PARTITIONDATE BETWEEN start_date AND end_date
ORDER BY g.DATE, a.ticker
LIMIT max_rows;
