# Architecture
Single ETL pipeline. Reads CSV from S3, transforms, writes to Postgres.
One internal consumer: a daily analytics dashboard. No model training.
