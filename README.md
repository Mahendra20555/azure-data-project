# azure-data-project

## AWS S3 Bronze Ingestion

This repository contains a GitHub Actions workflow to ingest data from an AWS S3 source bucket into an AWS S3 bronze location.

### Components

- Workflow: `.github/workflows/ingest-s3-to-s3.yml`
- Ingestion script: `scripts/ingest_s3_to_s3.py`

### Required GitHub secrets

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

### Workflow inputs

- `aws_region`: AWS region for the S3 buckets (default: `eu-north-1`)
- `source_s3_bucket`: source bucket name (default: `companieshouse-uk`)
- `source_s3_prefix`: source prefix/path to ingest
- `destination_s3_bucket`: destination bucket name for bronze data
- `destination_s3_prefix`: destination prefix for bronze data (default: `bronze/`)

### Notes

- The workflow copies objects from the source path to the destination bronze path using AWS S3.
- The script now validates access to both source and destination buckets before copying.
- Keep AWS credentials secret and do not commit them to source control.
