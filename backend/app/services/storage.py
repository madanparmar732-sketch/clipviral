"""Uploads finished clips to Supabase Storage and returns public links."""

import logging
import mimetypes
import os
import time

from app.config import settings
from app.supabase_client import get_admin

logger = logging.getLogger(__name__)


def upload_file_to_storage(local_path: str, storage_path: str) -> str:
    """
    Puts a file in the Supabase 'clips' bucket and returns its public URL.
    Tries 3 times, because the internet wobbles sometimes.
    """
    content_type = mimetypes.guess_type(storage_path)[0] or "application/octet-stream"
    with open(local_path, "rb") as f:
        data = f.read()

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            get_admin().storage.from_(settings.clips_bucket).upload(
                path=storage_path,
                file=data,
                file_options={"content-type": content_type, "x-upsert": "true"},
            )
            public_url = get_admin().storage.from_(settings.clips_bucket).get_public_url(storage_path)
            logger.info("Uploaded %s -> %s", local_path, public_url)
            return public_url
        except Exception as exc:
            last_error = exc
            logger.warning("Storage upload attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"Could not upload {storage_path} to Supabase Storage: {last_error}")


def download_file_from_storage(storage_path: str, local_path: str) -> bool:
    """Pull a file from the clips bucket to local disk. True on success."""
    try:
        data = get_admin().storage.from_(settings.clips_bucket).download(storage_path)
        if not data:
            return False
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with open(local_path, "wb") as fh:
            fh.write(data)
        return True
    except Exception:
        return False
