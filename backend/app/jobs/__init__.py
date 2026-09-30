"""The job intelligence pipeline: CSV ingestion -> skill extraction -> role matching ->
evidence (docs/06-job-intelligence.md).

    python -m app.cli.jobs ingest data/raw/job_postings.csv
    python -m app.cli.jobs process
    python -m app.cli.jobs evaluate
"""
