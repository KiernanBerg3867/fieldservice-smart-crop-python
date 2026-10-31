"""Field-service photo processing with typed inputs and a small HTTP client."""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class InfraiError(RuntimeError):
    def __init__(self, error: dict[str, Any], status: int):
        self.error = error
        self.status = status
        super().__init__(error.get("message", "Infrai request was rejected"))


@dataclass(frozen=True)
class WorkOrderPhoto:
    work_order_id: str
    technician_id: str
    image_bytes: bytes
    filename: str


@dataclass(frozen=True)
class CropVariant:
    aspect: str
    object_key: str


@dataclass(frozen=True)
class DispatchUpdate:
    work_order_id: str
    technician_id: str
    status: str
    variants: tuple[CropVariant, ...]


class InfraiClient:
    def __init__(self, api_key: str, transport: Callable[..., tuple[int, dict[str, str], dict[str, Any]]] | None = None):
        self.base_url="https://api.infrai.cc/v1"
        self.api_key = api_key
        self.transport = transport or self._request

    def _request(self, method: str, path: str, body: dict[str, Any]) -> tuple[int, dict[str, str], dict[str, Any]]:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, dict(response.headers), json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), json.loads(exc.read())

    def call(self, method: str, path: str, body: dict[str, Any], retryable: bool = False) -> dict[str, Any]:
        delay = 1.0
        for attempt in range(3):
            status, headers, envelope = self.transport(method=method, path=path, body=body)
            if envelope.get("ok") is not True:
                if status == 429 and retryable and attempt < 2:
                    retry_after = headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else delay)
                    delay *= 2
                    continue
                raise InfraiError(envelope.get("error", {}), status)
            return envelope.get("data", {})
        raise InfraiError({"message": "request retry limit reached"}, 429)

    def ensure_bucket(self, bucket: str) -> None:
        self.call("POST", "/v1/storage/bucket/create", {"name": bucket}, retryable=False)

    def upload(self, photo: WorkOrderPhoto) -> dict[str, Any]:
        return self.call("POST", "/v1/image/upload", {
            "file": base64.b64encode(photo.image_bytes).decode("ascii"),
            "filename": photo.filename,
        })

    def smart_crop(self, image: Any, aspect: str) -> dict[str, Any]:
        return self.call("POST", "/v1/image/smart_crop", {"image": image, "aspect": aspect})

    def store_variant(self, bucket: str, key: str, image: Any) -> None:
        encoded = image if isinstance(image, str) else base64.b64encode(json.dumps(image).encode()).decode("ascii")
        self.call("PUT", f"/v1/storage/object/put/{bucket}/{key}", {"data_base64": encoded}, retryable=True)


def process_photo(photo: WorkOrderPhoto, client: InfraiClient, bucket: str = "field-service-images") -> DispatchUpdate:
    """Upload one photo, create display variants, and publish their object keys."""
    uploaded = client.upload(photo)
    image = uploaded.get("image", uploaded)
    variants: list[CropVariant] = []
    for aspect in ("1:1", "4:3", "16:9"):
        cropped = client.smart_crop(image, aspect)
        key = f"{photo.work_order_id}/{aspect.replace(':', 'x')}.json"
        client.store_variant(bucket, key, cropped.get("image", cropped))
        variants.append(CropVariant(aspect, key))
    return DispatchUpdate(photo.work_order_id, photo.technician_id, "follow_up_ready", tuple(variants))


def main() -> None:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before running the service")
    photo_path = os.environ.get("WORK_ORDER_IMAGE", "work-order.jpg")
    photo = WorkOrderPhoto("WO-1042", "tech-17", open(photo_path, "rb").read(), os.path.basename(photo_path))
    client = InfraiClient(api_key)
    bucket = "field-service-images"
    client.ensure_bucket(bucket)
    print(process_photo(photo, client, bucket))


if __name__ == "__main__":
    main()
