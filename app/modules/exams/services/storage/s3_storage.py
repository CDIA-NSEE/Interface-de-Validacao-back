from __future__ import annotations

from app.core.settings import ObjectStorageSettings
from app.modules.exams.models import Exam


class S3ImageStorage:
    """Scaffolded S3/LocalStack-backed image storage. Disabled by default (S3_ENABLED=false).

    Not wired into the container until a real migration of image blobs to S3 happens.
    """

    def __init__(self, settings: ObjectStorageSettings) -> None:
        self._settings = settings
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self._settings.endpoint_url,
                region_name=self._settings.region,
                aws_access_key_id=self._settings.access_key_id,
                aws_secret_access_key=self._settings.secret_access_key,
            )
        return self._client

    def get_image(self, exam: Exam) -> dict | None:
        if not exam.metadata_id:
            return None

        client = self._get_client()
        key = f"exam-images/{exam.metadata_id}.bin"
        try:
            response = client.get_object(Bucket=self._settings.bucket, Key=key)
        except client.exceptions.NoSuchKey:
            return None

        return {
            "content": response["Body"].read(),
            "media_type": response.get("ContentType", "application/octet-stream"),
        }
