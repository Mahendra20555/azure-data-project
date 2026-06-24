import os
import sys
import boto3
from botocore.exceptions import ClientError


def list_s3_objects(bucket_name: str, prefix: str):
    s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'))
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get('Contents', []):
            yield obj['Key']


def validate_s3_bucket_access(bucket_name: str, allow_prefix: bool = False, prefix: str = ''):
    s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'))
    try:
        s3.head_bucket(Bucket=bucket_name)
    except ClientError as err:
        print(f"Unable to access S3 bucket '{bucket_name}': {err}")
        sys.exit(1)

    if allow_prefix and prefix:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix, MaxKeys=1)
        if response.get('KeyCount', 0) == 0:
            print(f"No objects found in '{bucket_name}/{prefix}'. Verify the prefix and bucket contents.")
            sys.exit(1)


def copy_s3_object(source_bucket: str, source_key: str, destination_bucket: str, destination_key: str):
    s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'))
    copy_source = {'Bucket': source_bucket, 'Key': source_key}
    try:
        s3.copy_object(
            CopySource=copy_source,
            Bucket=destination_bucket,
            Key=destination_key,
            MetadataDirective='COPY'
        )
    except ClientError as err:
        print(f"Error copying {source_bucket}/{source_key} to {destination_bucket}/{destination_key}: {err}")
        raise


def main():
    source_bucket = os.environ.get('SOURCE_S3_BUCKET')
    source_prefix = os.environ.get('SOURCE_S3_PREFIX', '')
    destination_bucket = os.environ.get('DESTINATION_S3_BUCKET')
    destination_prefix = os.environ.get('DESTINATION_S3_PREFIX', 'bronze/')

    if not source_bucket or not destination_bucket:
        print('SOURCE_S3_BUCKET and DESTINATION_S3_BUCKET environment variables are required.')
        sys.exit(1)

    validate_s3_bucket_access(source_bucket, allow_prefix=True, prefix=source_prefix)
    validate_s3_bucket_access(destination_bucket)

    print(f'Ingesting data from s3://{source_bucket}/{source_prefix} to s3://{destination_bucket}/{destination_prefix}')

    for key in list_s3_objects(source_bucket, source_prefix):
        destination_key = f"{destination_prefix.rstrip('/')}/{key}" if destination_prefix else key
        print(f'Copying {key} -> {destination_key}')
        copy_s3_object(source_bucket, key, destination_bucket, destination_key)

    print('Ingestion complete.')


if __name__ == '__main__':
    main()
