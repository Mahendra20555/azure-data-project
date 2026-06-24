import os
import re
import sys
import tempfile
import zipfile
import urllib.parse
from pathlib import Path

import boto3
import pandas as pd
import requests
from botocore.exceptions import ClientError


def resolve_zip_url(url: str) -> str:
    if url.lower().endswith('.zip'):
        return url

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    if 'zip' in response.headers.get('content-type', '').lower():
        return url

    matches = re.findall(r'href=["\']([^"\']+\.zip)["\']', response.text, flags=re.IGNORECASE)
    if not matches:
        raise ValueError(f'No ZIP download link found at {url}')

    return urllib.parse.urljoin(url, matches[0])


def download_zip(url: str, dest_path: Path):
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(dest_path, 'wb') as fd:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    fd.write(chunk)


def validate_bucket_access(s3_client, bucket_name: str):
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as err:
        print(f"Unable to access S3 bucket '{bucket_name}': {err}")
        sys.exit(1)


def upload_file(s3_client, local_path: Path, bucket_name: str, key: str):
    print(f'Uploading {local_path} -> s3://{bucket_name}/{key}')
    s3_client.upload_file(str(local_path), bucket_name, key)


def convert_csv_to_parquet(csv_path: Path, parquet_path: Path):
    print(f'Converting {csv_path} -> {parquet_path}')
    df = pd.read_csv(csv_path)
    df.to_parquet(parquet_path, index=False)
    return parquet_path


def collect_extracted_files(root_dir: Path):
    return [p for p in root_dir.rglob('*') if p.is_file()]


def output_key_for_path(root_dir: Path, file_path: Path, dest_prefix: str, output_format: str) -> str:
    relative = file_path.relative_to(root_dir).as_posix()
    if output_format == 'parquet' and file_path.suffix.lower() == '.csv':
        relative = str(Path(relative).with_suffix('.parquet')).replace('\\', '/')
    return f"{dest_prefix.rstrip('/')}/{relative}" if dest_prefix else relative


def main():
    download_url = os.environ.get('DOWNLOAD_URL')
    output_format = os.environ.get('OUTPUT_FORMAT', 'csv').lower()
    destination_bucket = os.environ.get('DESTINATION_S3_BUCKET')
    destination_prefix = os.environ.get('DESTINATION_S3_PREFIX', 'bronze/')
    aws_region = os.environ.get('AWS_REGION', 'eu-north-1')

    if not download_url or not destination_bucket:
        print('DOWNLOAD_URL and DESTINATION_S3_BUCKET environment variables are required.')
        sys.exit(1)

    if output_format not in {'csv', 'parquet'}:
        print('OUTPUT_FORMAT must be either "csv" or "parquet".')
        sys.exit(1)

    s3_client = boto3.client('s3', region_name=aws_region)
    validate_bucket_access(s3_client, destination_bucket)

    print(f'Resolving download URL: {download_url}')
    zip_url = resolve_zip_url(download_url)
    print(f'Downloading ZIP from: {zip_url}')

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        zip_path = tmpdir_path / 'source.zip'
        download_zip(zip_url, zip_path)

        extracted_dir = tmpdir_path / 'extracted'
        extracted_dir.mkdir()
        with zipfile.ZipFile(zip_path, 'r') as archive:
            archive.extractall(extracted_dir)

        files = collect_extracted_files(extracted_dir)
        if not files:
            print('No files found inside the downloaded ZIP archive.')
            sys.exit(1)

        for file_path in files:
            if output_format == 'csv' and file_path.suffix.lower() == '.csv':
                upload_path = file_path
            elif output_format == 'csv' and file_path.suffix.lower() == '.parquet':
                print(f'Skipping parquet file {file_path} because OUTPUT_FORMAT=csv.')
                continue
            elif output_format == 'parquet' and file_path.suffix.lower() == '.csv':
                upload_path = tmpdir_path / 'converted' / file_path.with_suffix('.parquet').name
                upload_path.parent.mkdir(parents=True, exist_ok=True)
                convert_csv_to_parquet(file_path, upload_path)
            elif output_format == 'parquet' and file_path.suffix.lower() == '.parquet':
                upload_path = file_path
            else:
                print(f'Skipping unsupported file type: {file_path}')
                continue

            key = output_key_for_path(extracted_dir, file_path, destination_prefix, output_format)
            upload_file(s3_client, upload_path, destination_bucket, key)

    print('URL ingestion complete.')


if __name__ == '__main__':
    main()
