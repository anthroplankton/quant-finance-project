-- ARCHIVED REFERENCE ONLY.
--
-- This BigQuery template is not part of the selected zero-cost implementation
-- route because the current project should not require Google Cloud,
-- BigQuery, billing setup, or cloud credentials. Keep it only as a reference
-- for the technically feasible but rejected BigQuery path.
--
-- GDELT GKG one-company prototype query template.
-- Placeholder variables rendered by scripts/probe_gdelt_metadata.py:
--   start_date
--   end_date
--   company_alias
--   ticker
--   max_rows
--
-- This template returns metadata only. Do not store article text.

DECLARE start_date DATE DEFAULT DATE(${start_date_literal});
DECLARE end_date DATE DEFAULT DATE(${end_date_literal});
DECLARE company_alias STRING DEFAULT ${company_alias_literal};
DECLARE ticker STRING DEFAULT ${ticker_literal};
DECLARE max_rows INT64 DEFAULT ${max_rows};

SELECT
  DocumentIdentifier AS document_identifier,
  SourceCommonName AS source,
  PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING)) AS timestamp,
  SourceCollectionIdentifier AS source_collection_identifier,
  company_alias AS matched_company_alias,
  ticker AS matched_ticker,
  FORMAT_DATE('%Y-%m-%d', start_date) AS query_start_date,
  FORMAT_DATE('%Y-%m-%d', end_date) AS query_end_date,
  'gdelt_gkg_one_company_template' AS query_method
FROM `gdelt-bq.gdeltv2.gkg_partitioned`
WHERE _PARTITIONDATE BETWEEN start_date AND end_date
  AND (
    STRPOS(LOWER(IFNULL(V2Organizations, '')), LOWER(company_alias)) > 0
    OR STRPOS(LOWER(IFNULL(DocumentIdentifier, '')), LOWER(company_alias)) > 0
  )
ORDER BY DATE
LIMIT max_rows;
