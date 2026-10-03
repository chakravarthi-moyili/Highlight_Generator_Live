import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
import os
import time
from src.core.config import S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET_NAME, S3_REGION,S3_PREFIX, CLOUDFRONT_URL
from src.core.logging_config import get_logger

logger = get_logger(__name__)

class CloudStorageClient:
    def __init__(self):
        """
        Initializes the S3Uploader instance by reading credentials and configuration
        from environment variables.
        """
        self.s3_access_key = S3_ACCESS_KEY
        self.s3_secret_key = S3_SECRET_KEY
        self.bucket_name = S3_BUCKET_NAME
        self.region = S3_REGION
        self.s3_prefix = S3_PREFIX
        self.cloudfront_url = CLOUDFRONT_URL

        if not self.s3_access_key or not self.s3_secret_key or not self.bucket_name or not self.cloudfront_url:
            raise ValueError("S3 credentials or bucket name not set in environment variables.")

        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.s3_access_key,
            aws_secret_access_key=self.s3_secret_key
        )
    # def upload_to_s3(self, file_path, s3_key):
    #         """
    #         Uploads a file to the specified S3 bucket.

    #         :param file_path: Local path to the file to be uploaded.
    #         :param s3_key: The key under which the file will be stored in S3.
    #         :raises FileNotFoundError: If the file does not exist.
    #         :raises NoCredentialsError: If AWS credentials are not available.
    #         :raises PartialCredentialsError: If incomplete AWS credentials are provided.
    #         """
    #         if not os.path.exists(file_path):
    #             raise FileNotFoundError(f"The file {file_path} does not exist.")

    #         try:
    #             self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
    #             print(f"File {file_path} uploaded to {self.bucket_name}/{s3_key}.")
    #             return f"{self.cloudfront_url}/{s3_key}"
    #         except NoCredentialsError:
    #             raise NoCredentialsError("AWS credentials not available.")
    #         except PartialCredentialsError:
    #             raise PartialCredentialsError("Incomplete AWS credentials provided.")
            
    def upload_to_s3(self, file_path, s3_key):
            """
            Uploads a file to the specified S3 bucket.

            :param file_path: Local path to the file to be uploaded.
            :param s3_key: The key under which the file will be stored in S3.
            :raises FileNotFoundError: If the file does not exist.
            :raises NoCredentialsError: If AWS credentials are not available.
            :raises PartialCredentialsError: If incomplete AWS credentials are provided.
            """
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"The file {file_path} does not exist.")

            try:
                timestamp = str(int(time.time()))
                self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
                self.s3_client.put_object_tagging(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Tagging={'TagSet': [
                        {'Key': 'Created', 'Value': timestamp},
                        {'Key': 'ManagedBy', 'Value': 'LiveHighlights'}
                    ]}
                )
                logger.info("File %s uploaded to %s/%s.", file_path, self.bucket_name, s3_key)
                return f"{self.cloudfront_url}/{s3_key}"
            except (NoCredentialsError, PartialCredentialsError):
                # These botocore errors take keyword args only, so re-raising them
                # with a message (NoCredentialsError("...")) raised TypeError and
                # masked the real credentials problem. Log and re-raise as-is.
                logger.exception("AWS credentials unavailable or incomplete while uploading %s", file_path)
                raise

    def delete_old_live_highlights(self, age_days, timeout_seconds=30):
        """
        Deletes objects under live-highlights/ prefix that are older than `age_days`,
        based on S3 object tagging.

        Args:
            age_days: Number of days to keep (delete older than this)
            timeout_seconds: Max seconds to spend on this operation (default: 30s)

        Returns:
            int: Number of objects deleted, or -1 if operation timed out
        """
        prefix = self.s3_prefix
        now = int(time.time())
        cutoff = now - int(age_days * 86400)
        start_time = time.time()

        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            deleted = 0

            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                # Check timeout after each page
                if time.time() - start_time > timeout_seconds:
                    logger.warning("S3 cleanup timed out after %d seconds, processed %d deletions", timeout_seconds, deleted)
                    return deleted

                contents = page.get('Contents', [])

                for obj in contents:
                    # Check timeout for each object too
                    if time.time() - start_time > timeout_seconds:
                        logger.warning("S3 cleanup timed out after %d seconds, processed %d deletions", timeout_seconds, deleted)
                        return deleted

                    key = obj['Key']
                    try:
                        tagging = self.s3_client.get_object_tagging(Bucket=self.bucket_name, Key=key)
                        tags = {tag['Key']: tag['Value'] for tag in tagging['TagSet']}

                        managed_by = tags.get('ManagedBy')
                        if tags.get('ManagedBy') != 'LiveHighlights':
                            logger.debug("Skipping %s, ManagedBy tag is %r", key, managed_by)
                            continue

                        created_str = tags.get('Created')
                        if not created_str:
                            logger.debug("Skipping %s, no 'Created' tag found", key)
                            continue

                        try:
                            created_time = int(created_str)
                        except ValueError:
                            logger.warning("Skipping %s, invalid 'Created' tag value: %s", key, created_str)
                            continue

                        logger.debug("Checking %s: created_time=%s, cutoff=%s", key, created_time, cutoff)
                        if created_time < cutoff:
                            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
                            logger.info("Deleted: %s", key)
                            deleted += 1
                        else:
                            logger.debug("Keeping %s, not old enough", key)

                    except Exception as e:
                        logger.error("Skipping %s due to error: %s", key, e)

            logger.info("Deleted %s expired live-highlight objects.", deleted)
            return deleted

        except Exception as e:
            logger.error("Error during S3 cleanup: %s. Continuing without cleanup.", e)
            return -1

      
    # def delete_prefix(self, prefix):
    #     try:
    #         paginator = self.s3_client.get_paginator('list_objects_v2')
    #         page_iterator = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

    #         deleted_any = False
    #         for page in page_iterator:
    #             if 'Contents' in page:
    #                 objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
    #                 self.s3_client.delete_objects(
    #                     Bucket=self.bucket_name,
    #                     Delete={'Objects': objects_to_delete}
    #                 )
    #                 for obj in objects_to_delete:
    #                     print(f"Deleted {obj['Key']} from {self.bucket_name}.")
    #                 deleted_any = True

    #         if not deleted_any:
    #             print(f"No objects found with prefix {prefix} in bucket {self.bucket_name}.")
    #     except Exception as e:
    #         print(f"Error deleting objects with prefix {prefix}: {e}")


    # def delete_prefix(self, prefix):
    #     """
    #     Deletes all objects with the specified prefix in the S3 bucket.

    #     :param prefix: The prefix of the objects to delete.
    #     """
    #     try:
    #         response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
    #         if 'Contents' in response:
    #             for obj in response['Contents']:
    #                 self.s3_client.delete_object(Bucket=self.bucket_name, Key=obj['Key'])
    #                 print(f"Deleted {obj['Key']} from {self.bucket_name}.")
    #         else:
    #             print(f"No objects found with prefix {prefix} in bucket {self.bucket_name}.")
    #     except Exception as e:
    #         print(f"Error deleting objects with prefix {prefix}: {e}")






















# import boto3
# from src.core.config import S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET

# def upload_to_s3(file_path):
#     s3 = boto3.client(
#         's3',
#         aws_access_key_id=S3_ACCESS_KEY,
#         aws_secret_access_key=S3_SECRET_KEY,
#     )
#     import os
#     key = os.path.basename(file_path)
#     s3.upload_file(file_path, S3_BUCKET, key, ExtraArgs={'ACL': 'public-read'})
#     url = f"https://{S3_BUCKET}.s3.amazonaws.com/{key}"
#     return url
