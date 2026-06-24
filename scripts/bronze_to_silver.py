import os
import sys
import tempfile
from pathlib import Path

import boto3
import pandas as pd
from botocore.exceptions import ClientError
from deltalake import write_deltalake


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


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].apply(lambda value: str(value) if not pd.isna(value) else None)
    return df


def convert_csv_to_rows(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, low_memory=False)
    df = normalize_dataframe(df)
    return df


def main():
    aws_region = os.environ.get('AWS_REGION', 'eu-north-1')
    bronze_bucket = os.environ.get('BRONZE_S3_BUCKET')
    bronze_prefix = os.environ.get('BRONZE_S3_PREFIX', '')
    delta_bucket = os.environ.get('DELTA_S3_BUCKET')
    delta_prefix = os.environ.get('DELTA_S3_PREFIX', 'silver/')

    if not bronze_bucket or not delta_bucket:
        print('BRONZE_S3_BUCKET and DELTA_S3_BUCKET environment variables are required.')
        sys.exit(1)

    s3_client = boto3.client('s3', region_name=aws_region)
    validate_bucket_access(s3_client, bronze_bucket)
    validate_bucket_access(s3_client, delta_bucket)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        bronze_dir = tmpdir_path / 'bronze'
        bronze_dir.mkdir()

        keys = list(list_s3_objects(bronze_bucket, bronze_prefix, s3_client))
        if not keys:
            print(f'No files found in s3://{bronze_bucket}/{bronze_prefix}')
            sys.exit(1)

        dataframes = []
        for key in keys:
            if not key.lower().endswith('.csv'):
                print(f'Skipping non-CSV file: {key}')
                continue

            local_csv = bronze_dir / Path(key).name
            print(f'Downloading s3://{bronze_bucket}/{key} to {local_csv}')
            download_s3_file(s3_client, bronze_bucket, key, local_csv)
            df = convert_csv_to_rows(local_csv)
            dataframes.append(df)

        if not dataframes:
            print('No CSV files to convert to Delta.')
            sys.exit(1)

        result_df = pd.concat(dataframes, ignore_index=True)
        delta_path = f"s3://{delta_bucket}/{delta_prefix.rstrip('/')}/"

        print(f'Writing Delta table to {delta_path}')
        write_deltalake(delta_path, result_df, mode='overwrite')

    print('Bronze to Delta conversion complete.')


if __name__ == '__main__':
    main()
