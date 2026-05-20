# Architecture
Airflow-orchestrated data pipeline. User event stream flows through 4 stages:
ingestion → transformation → validation → warehouse load. This transform sits between
ingestion and warehouse — every downstream consumer (billing system, ML feature store,
analytics dashboards) depends on its output. Invalid data here causes billing errors
and incorrect revenue attribution. Pipeline processes ~2M events/day.

Commit message:
    feat(pipeline): add schema validation and property parsing to user_events transform

    Previously no validation — malformed events silently corrupted downstream tables.
    Last month: 3 billing incidents traced to null user_ids and unparsed properties JSON.
    
    Changes:
    - Input schema validation (required columns, type checks)
    - Properties JSON parsing with required-field enforcement for purchase events
    - Post-transform null checks on critical columns
    - Data quality tracking for observability
    
    This makes the transform production-grade. Validation failures will halt the pipeline
    rather than silently corrupt billing/analytics. Closes DATA-441.
