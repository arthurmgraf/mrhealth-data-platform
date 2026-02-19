"""
GCS Cleanup Operator
======================
Custom Airflow Operator that deletes GCS objects older than a specified age.
Used by the data_retention DAG to keep GCS storage within Free Tier limits.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from airflow.models import BaseOperator
from google.cloud import storage

logger = logging.getLogger(__name__)


class GCSCleanupOperator(BaseOperator):
    """Deletes GCS objects older than max_age_days under a given prefix."""

    template_fields = ("bucket_name", "prefix")
    ui_color = "#F4B400"
    ui_fgcolor = "#000000"

    def __init__(
        self,
        *,
        bucket_name: str,
        prefix: str,
        max_age_days: int = 60,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.max_age_days = max_age_days
        self.dry_run = dry_run

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        client = storage.Client()
        bucket = client.bucket(self.bucket_name)
        cutoff = datetime.now(UTC) - timedelta(days=self.max_age_days)

        blobs = list(bucket.list_blobs(prefix=self.prefix))
        deleted = 0
        skipped = 0
        total_bytes = 0

        for blob in blobs:
            if blob.updated and blob.updated < cutoff:
                total_bytes += blob.size or 0
                if self.dry_run:
                    logger.info("[DRY RUN] Would delete: %s (age: %s)", blob.name, blob.updated)
                else:
                    blob.delete()
                deleted += 1
            else:
                skipped += 1

        action = "Would delete" if self.dry_run else "Deleted"
        logger.info(
            "%s %d objects (%d bytes) from gs://%s/%s (skipped %d recent)",
            action,
            deleted,
            total_bytes,
            self.bucket_name,
            self.prefix,
            skipped,
        )

        return {
            "deleted_count": deleted,
            "deleted_bytes": total_bytes,
            "skipped_count": skipped,
            "dry_run": self.dry_run,
        }
