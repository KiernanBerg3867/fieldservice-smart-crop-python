import base64
from typing import Any

from src.smart_crop_service import InfraiClient, WorkOrderPhoto, process_photo


def test_photo_becomes_three_dispatch_variants() -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def transport(*, method: str, path: str, body: dict[str, Any]):
        calls.append((method, path, body))
        if path == "/v1/image/upload":
            assert body["filename"] == "arrival.jpg"
            assert body["file"] == base64.b64encode(b"photo").decode()
            return 200, {}, {"ok": True, "data": {"image": "uploaded-image"}}
        if path == "/v1/image/smart_crop":
            return 200, {}, {"ok": True, "data": {"image": "cropped-image"}}
        return 200, {}, {"ok": True, "data": {}}

    client = InfraiClient("test-key", transport=transport)
    client.ensure_bucket("field-service-images")
    result = process_photo(WorkOrderPhoto("WO-7", "tech-2", b"photo", "arrival.jpg"), client)

    assert result.status == "follow_up_ready"
    assert [variant.aspect for variant in result.variants] == ["1:1", "4:3", "16:9"]
    assert [path for _, path, _ in calls if path.startswith("/v1/storage/object/put/")] == [
        "/v1/storage/object/put/field-service-images/WO-7/1x1.json",
        "/v1/storage/object/put/field-service-images/WO-7/4x3.json",
        "/v1/storage/object/put/field-service-images/WO-7/16x9.json",
    ]
