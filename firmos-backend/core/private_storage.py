"""Private evidence storage with an explicit local/test-only fallback."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import httpx

from core.config import get_settings


LOCAL_ROOT = Path("uploads")


class StorageUnavailable(RuntimeError):
    """Storage could not accept or resolve private evidence."""


def _safe_object_path(object_path: str) -> str:
    path = PurePosixPath(object_path)
    if path.is_absolute() or ".." in path.parts:
        raise StorageUnavailable("Invalid evidence object path.")
    return path.as_posix()


def _local_path(bucket: str, object_path: str) -> Path:
    return LOCAL_ROOT / bucket / _safe_object_path(object_path)


async def store_private_evidence(
    bucket: str, object_path: str, content: bytes, content_type: str
) -> str:
    """Store evidence privately or raise; production never uses local files."""
    settings = get_settings()
    object_path = _safe_object_path(object_path)
    if settings.supabase_url and settings.supabase_service_key:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{settings.supabase_url}/storage/v1/object/{bucket}/{object_path}",
                    headers={
                        "Authorization": f"Bearer {settings.supabase_service_key}",
                        "Content-Type": content_type,
                    },
                    content=content,
                )
        except httpx.HTTPError as exc:
            raise StorageUnavailable("Private evidence storage is temporarily unavailable.") from exc
        if response.status_code in {200, 201}:
            return f"storage://{bucket}/{object_path}"
        raise StorageUnavailable("Private evidence storage rejected the upload.")
    if not settings.local_storage_allowed:
        raise StorageUnavailable("Private evidence storage is not configured.")
    path = _local_path(bucket, object_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return f"local://{bucket}/{object_path}"


async def create_signed_url(stored_url: str) -> str:
    """Create a short-lived remote URL; local files must be streamed by the API."""
    if not stored_url.startswith("storage://"):
        raise StorageUnavailable("Evidence is not stored in private remote storage.")
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise StorageUnavailable("Private evidence storage is not configured.")
    bucket, object_path = stored_url.removeprefix("storage://").split("/", 1)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{settings.supabase_url}/storage/v1/object/sign/{bucket}/{object_path}",
                headers={"Authorization": f"Bearer {settings.supabase_service_key}"},
                json={"expiresIn": 300},
            )
    except httpx.HTTPError as exc:
        raise StorageUnavailable("Private evidence storage is temporarily unavailable.") from exc
    signed_path = response.json().get("signedURL") if response.status_code == 200 else None
    if not signed_path:
        raise StorageUnavailable("Private evidence storage could not prepare a download.")
    return f"{settings.supabase_url}/storage/v1{signed_path}"


def local_evidence_path(stored_url: str) -> Path:
    """Return a local test/development evidence path after validating its URL."""
    settings = get_settings()
    if not settings.local_storage_allowed or not stored_url.startswith("local://"):
        raise StorageUnavailable("Local evidence access is unavailable.")
    bucket, object_path = stored_url.removeprefix("local://").split("/", 1)
    path = _local_path(bucket, object_path)
    if not path.is_file():
        raise StorageUnavailable("Local evidence is unavailable.")
    return path
