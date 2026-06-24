import os
import sys
import tempfile
from pathlib import Path

import boto3
import pandas as pd
from botocore.exceptions import ClientError


def list_s3_objects(bucket_name: str, prefix: str, s3_client):
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get('Contents', []):
            yield obj['Key']


def validate_bucket_access(s3_client, bucket_name: str):
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as err:
        print(f"Unable to access S3 bucket '{bucket_name}': {err}")
        sys.exit(1)


def download_s3_file(s3_client, bucket_name: str, key: str, local_path: Path):
    local_path.parent.mkdir(parents=True, exist_ok=True)
    s3_client.download_file(bucket_name, key, str(local_path))


def upload_s3_file(s3_client, local_path: Path, bucket_name: str, key: str):
    local_path.parent.mkdir(parents=True, exist_ok=True)
    print(f'Uploading {local_path} -> s3://{bucket_name}/{key}')
    s3_client.upload_file(str(local_path), bucket_name, key)


def normalize_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include=['object']).columns:
        mask = df[col].isna()
        df[col] = df[col].apply(
            lambda value: value.decode('utf-8', errors='ignore')
            if isinstance(value, (bytes, bytearray))
            else str(value)
            if not pd.isna(value)
            else None
        )
        df.loc[mask, col] = None
    return df


def convert_csv_to_parquet(csv_path: Path, parquet_path: Path):
    print(f'Converting {csv_path} -> {parquet_path}')
    df = pd.read_csv(csv_path, low_memory=False)
    df = normalize_object_columns(df)
    df.to_parquet(parquet_path, index=False)
    return parquet_path


def output_key_for_path(root_dir: Path, file_path: Path, dest_prefix: str) -> str:
    relative = file_path.relative_to(root_dir).with_suffix('.parquet').as_posix()
    return f"{dest_prefix.rstrip('/')}/{relative}" if dest_prefix else relative


def main():
    aws_region = os.environ.get('AWS_REGION', 'eu-north-1')
    bronze_bucket = os.environ.get('BRONZE_S3_BUCKET')
    bronze_prefix = os.environ.get('BRONZE_S3_PREFIX', '')
    silver_bucket = os.environ.get('SILVER_S3_BUCKET')
    silver_prefix = os.environ.get('SILVER_S3_PREFIX', 'silver/')

    if not bronze_bucket or not silver_bucket:
        print('BRONZE_S3_BUCKET and SILVER_S3_BUCKET environment variables are required.')
        sys.exit(1)

    s3_client = boto3.client('s3', region_name=aws_region)
    validate_bucket_access(s3_client, bronze_bucket)
    validate_bucket_access(s3_client, silver_bucket)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        download_dir = tmpdir_path / 'bronze'
        parquet_dir = tmpdir_path / 'silver'
        download_dir.mkdir()
        parquet_dir.mkdir()

        keys = list(list_s3_objects(bronze_bucket, bronze_prefix, s3_client))
        if not keys:
            print(f'No files found in s3://{bronze_bucket}/{bronze_prefix}')
            sys.exit(1)

        for key in keys:
            if not key.lower().endswith('.csv'):
                print(f'Skipping non-CSV file: {key}')
                continue

            local_csv = download_dir / Path(key).name
            print(f'Downloading s3://{bronze_bucket}/{key} to {local_csv}')
            download_s3_file(s3_client, bronze_bucket, key, local_csv)

            local_parquet = parquet_dir / local_csv.with_suffix('.parquet').name
            convert_csv_to_parquet(local_csv, local_parquet)

            destination_key = output_key_for_path(parquet_dir, local_parquet, silver_prefix)
            upload_s3_file(s3_client, local_parquet, silver_bucket, destination_key)

    print('Bronze to silver conversion complete.')


if __name__ == '__main__':
    main()
