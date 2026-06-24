# azure-data-project

## AWS S3 Bronze Ingestion

This repository contains GitHub Actions workflows to:

1. ingest Companies House ZIP data from a URL into an AWS S3 bronze location
2. convert bronze CSV data into a Delta Lake silver table in AWS S3

### Workflows

- Bronze ingestion workflow: `.github/workflows/ingest-s3-to-s3.yml`
- Bronze-to-silver transformation workflow: `.github/workflows/bronze-to-silver.yml`
- ECR container run workflow: `.github/workflows/run-ecr-container.yml`

### Scripts

- `scripts/ingest_url_to_s3.py` — download ZIP from URL, extract files, and upload CSV or Parquet to bronze
- `scripts/ingest_s3_to_s3.py` — copy data between S3 prefixes
- `scripts/bronze_to_silver.py` — convert bronze CSV files to Delta and write the `_delta_log` table to silver

### Required GitHub secrets

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

### Bronze ingestion workflow inputs

- `aws_region`: AWS region for the S3 buckets (default: `eu-north-1`)
- `download_url`: URL to download the Companies House ZIP data from
- `output_format`: upload data as `csv` or `parquet`
- `destination_s3_bucket`: destination bucket name for bronze data
- `destination_s3_prefix`: destination prefix for bronze data (default: `bronze/`)

### Bronze-to-silver workflow inputs

- `aws_region`: AWS region for the S3 buckets (default: `eu-north-1`)
- `bronze_s3_bucket`: S3 bucket name where bronze data is stored
- `bronze_s3_prefix`: S3 prefix for bronze data files (default: `bronze/`)
- `silver_s3_bucket`: S3 bucket name for the Delta silver table
- `silver_s3_prefix`: S3 prefix for the Delta table files (default: `silver/`)

### Notes

- `scripts/ingest_url_to_s3.py` can download and extract a Companies House ZIP and upload CSV or Parquet files to bronze.
- `scripts/bronze_to_silver.py` converts bronze CSV files into a Delta Lake table and writes `_delta_log` metadata under silver.
- `.github/workflows/run-ecr-container.yml` pulls an ECR image and runs a container command with AWS/S3 credentials.
- The workflows validate S3 bucket access before copying or uploading.
- Keep AWS credentials secret and do not commit them to source control.

### ECR container workflow example

Use the `run-ecr-container` workflow to execute container-based jobs from your ECR image.

Inputs:
- `aws_region`: AWS region for ECR and S3 access (default: `eu-north-1`)
- `ecr_image`: ECR image URL (default: `207448370045.dkr.ecr.eu-north-1.amazonaws.com/companieshouse:latest`)
- `command`: command to run inside the container (default: `python scripts/bronze_to_silver.py`)
- `bronze_s3_bucket`: bucket with bronze data
- `bronze_s3_prefix`: prefix for bronze data (default: `bronze/`)
- `delta_s3_bucket`: bucket for Delta silver data
- `delta_s3_prefix`: prefix for Delta silver data (default: `silver/`)
