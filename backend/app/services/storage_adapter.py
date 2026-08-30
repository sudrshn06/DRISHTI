import io
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.services.image_store import (
    store_capture_image,
    get_capture_image,
    get_image_by_hash,
    get_image_metadata
)

logger = logging.getLogger(__name__)

class StorageAdapter(ABC):
    """
    Abstract storage adapter interface for package capture image assets.
    Establishes the boundary for durable S3/MinIO object storage (Phase 7B)
    without entangling domain logic or legal rules.
    """

    @abstractmethod
    def store(self, key: str, sha256_hash: str, data: bytes, media_type: str = "image/jpeg", width: Optional[int] = None, height: Optional[int] = None) -> bool:
        """Stores image bytes and returns whether durable storage succeeded."""
        pass

    @abstractmethod
    def retrieve(self, key: str) -> Optional[bytes]:
        """Retrieves raw image bytes by key."""
        pass

    @abstractmethod
    def retrieve_by_hash(self, sha256_hash: str) -> Optional[bytes]:
        """Retrieves raw image bytes by SHA-256 hash."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Checks whether an object exists in storage."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Deletes an object from storage."""
        pass

    @abstractmethod
    def delete_inspection_objects(self, inspection_id: str) -> int:
        """Deletes all objects belonging to a specific inspection."""
        pass

class MinioStorageAdapter(StorageAdapter):
    """
    Durable S3-compatible MinIO object storage adapter for DRISHTI.
    Persists original package capture images under deterministic, non-product-specific object keys.
    Maintains a single physical binary object per capture without duplicate storage.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        secure: Optional[bool] = None
    ):
        self.endpoint = endpoint or settings.minio_endpoint
        self.access_key = access_key if access_key is not None else settings.minio_access_key
        self.secret_key = secret_key if secret_key is not None else settings.minio_secret_key
        self.bucket_name = bucket_name or settings.minio_bucket_name
        self.secure = secure if secure is not None else settings.minio_secure
        self._client = None
        self._initialized = False

    def _get_client(self):
        if self._client is None:
            if not self.access_key or not self.secret_key:
                logger.debug("MinIO access_key or secret_key is not configured in settings/environment.")
                return None
            try:
                from minio import Minio
                self._client = Minio(
                    self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=self.secure
                )
            except Exception as e:
                logger.warning(f"Failed to initialize MinIO client: {e}")
                self._client = None
        return self._client

    def _ensure_bucket(self):
        if not self._initialized:
            client = self._get_client()
            if client:
                try:
                    if not client.bucket_exists(self.bucket_name):
                        client.make_bucket(self.bucket_name)
                    self._initialized = True
                except Exception as e:
                    logger.warning(f"Failed to ensure MinIO bucket {self.bucket_name}: {e}")

    def store(self, key: str, sha256_hash: str, data: bytes, media_type: str = "image/jpeg", width: Optional[int] = None, height: Optional[int] = None) -> bool:
        """
        Stores image bytes in MinIO under the single canonical object key.
        Does NOT store duplicate binary objects under secondary hash keys.
        """
        # Also store in local in-memory session cache for fast immediate lookups
        store_capture_image(
            capture_id=key,
            sha256_hash=sha256_hash,
            image_bytes=data,
            media_type=media_type,
            width=width,
            height=height
        )

        client = self._get_client()
        if not client:
            return False

        self._ensure_bucket()
        try:
            data_stream = io.BytesIO(data)
            client.put_object(
                bucket_name=self.bucket_name,
                object_name=key,
                data=data_stream,
                length=len(data),
                content_type=media_type,
                metadata={"sha256": sha256_hash}
            )
            return True
        except Exception as e:
            logger.error(f"Error storing object {key} in MinIO: {e}")
            raise

    def retrieve(self, key: str) -> Optional[bytes]:
        """Retrieves raw image bytes by object key from MinIO or fallback session cache."""
        client = self._get_client()
        if client:
            try:
                response = client.get_object(self.bucket_name, key)
                try:
                    return response.read()
                finally:
                    response.close()
                    response.release_conn()
            except Exception as e:
                logger.debug(f"Object {key} not found in MinIO: {e}")

        # Fallback to local in-memory session store
        return get_capture_image(key)

    def retrieve_by_hash(self, sha256_hash: str) -> Optional[bytes]:
        """
        Resolves raw image bytes by SHA-256 cryptographic hash without duplicate storage.
        First checks in-memory cache, then resolves object_key via PostgreSQL database index.
        """
        if not sha256_hash:
            return None

        # 1. Fallback to local session store
        in_mem = get_image_by_hash(sha256_hash)
        if in_mem:
            return in_mem

        # 2. Resolve object_key from PostgreSQL captures index
        try:
            from app.db.session import SessionLocal
            from app.repositories.inspection_repository import InspectionRepository
            with SessionLocal() as db:
                cap = InspectionRepository.get_capture_by_hash(db, sha256_hash)
                if cap and cap.object_key:
                    return self.retrieve(cap.object_key)
        except Exception as e:
            logger.debug(f"Error resolving hash {sha256_hash} via database: {e}")

        return None

    def exists(self, key: str) -> bool:
        """Checks whether an object exists in MinIO or in-memory cache."""
        client = self._get_client()
        if client:
            try:
                client.stat_object(self.bucket_name, key)
                return True
            except Exception:
                return False
        return get_capture_image(key) is not None

    def delete(self, key: str) -> bool:
        """Deletes a single object from MinIO safely and idempotently."""
        from app.services.image_store import remove_capture_image
        remove_capture_image(key)
        client = self._get_client()
        if client:
            try:
                client.remove_object(self.bucket_name, key)
                return True
            except Exception as e:
                logger.warning(f"Error removing object {key} from MinIO: {e}")
                return False
        return True

    def delete_inspection_objects(self, inspection_id: str) -> int:
        """
        Safely deletes all objects associated with a given inspection prefix.
        Guarantees that objects belonging to other inspections remain completely untouched.
        """
        client = self._get_client()
        if not client or not inspection_id:
            return 0

        from app.services.image_store import remove_capture_image
        prefix = f"inspections/{inspection_id}/"
        deleted_count = 0
        try:
            objects = list(client.list_objects(self.bucket_name, prefix=prefix, recursive=True))
            for obj in objects:
                client.remove_object(self.bucket_name, obj.object_name)
                remove_capture_image(obj.object_name)
                deleted_count += 1
        except Exception as e:
            logger.warning(f"Error cleaning inspection objects for prefix {prefix}: {e}")

        return deleted_count

class TemporarySessionStorageAdapter(StorageAdapter):
    """
    In-memory temporary session storage adapter fallback.
    """

    def store(self, key: str, sha256_hash: str, data: bytes, media_type: str = "image/jpeg", width: Optional[int] = None, height: Optional[int] = None) -> bool:
        store_capture_image(
            capture_id=key,
            sha256_hash=sha256_hash,
            image_bytes=data,
            media_type=media_type,
            width=width,
            height=height
        )
        return False

    def retrieve(self, key: str) -> Optional[bytes]:
        return get_capture_image(key)

    def retrieve_by_hash(self, sha256_hash: str) -> Optional[bytes]:
        return get_image_by_hash(sha256_hash)

    def exists(self, key: str) -> bool:
        return get_capture_image(key) is not None

    def delete(self, key: str) -> bool:
        return True

    def delete_inspection_objects(self, inspection_id: str) -> int:
        return 0

# Default active adapter instance is MinIO
default_storage_adapter: StorageAdapter = MinioStorageAdapter()
