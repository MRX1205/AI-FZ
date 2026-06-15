from pathlib import Path

import pytest

from app.services import product_image_recognition_agent as product_image_module
from app.services.product_image_recognition_agent import product_image_recognition_agent


def test_product_image_recognition_agent_supports_legacy_products_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    upload_root = tmp_path / "uploads"
    image_path = upload_root / "products" / "merchants" / "legacy.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(product_image_module, "UPLOAD_BASE", upload_root)

    data_url = product_image_recognition_agent._product_image_data_url(
        "/uploads/products/merchants/legacy.png",
    )

    assert data_url.startswith("data:image/png;base64,")


def test_product_image_recognition_agent_supports_absolute_upload_urls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    upload_root = tmp_path / "uploads"
    image_path = upload_root / "merchants" / "absolute.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(product_image_module, "UPLOAD_BASE", upload_root)

    data_url = product_image_recognition_agent._product_image_data_url(
        "https://merchant.lyhlz.cn/uploads/merchants/absolute.png?ts=1",
    )

    assert data_url.startswith("data:image/png;base64,")
