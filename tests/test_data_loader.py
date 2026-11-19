import json
from pathlib import Path

import pytest

from bank_simulator.data_loader import ContentLoadError, DataLoader
from bank_simulator.models import ClientProfile
from bank_simulator.services.content_service import ContentService


def test_load_default_data_from_another_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    loader = DataLoader()
    clients = loader.load_clients()
    products = loader.load_products()
    hidden_needs = loader.load_hidden_needs(clients, products)

    assert {profile.id: profile.name for profile in clients} == {
        "maryam": "Maryam Al-Kuwari",
        "mohamed": "Mohamed Al-Ansari",
    }
    assert {record.client_id for record in hidden_needs} == {"maryam", "mohamed"}
    assert {product.name for product in products} == {
        "Business Flex Credit",
        "Islamic Trade Finance",
        "Business Cash Management",
        "Goal Saver Account",
        "Everyday Access Account",
    }


def test_public_loading_works_without_private_files(editable_data):
    for path in (editable_data / "hidden_needs").glob("*.json"):
        path.unlink()

    loader = DataLoader(editable_data)
    assert len(loader.load_clients()) == 2
    assert len(loader.load_products()) == 5
    with pytest.raises(ContentLoadError, match="missing private profiles for: maryam, mohamed"):
        ContentService(editable_data)


def test_public_content_never_returns_private_fields(content):
    private_markers = ("QAR 15,000", "Sharia-compliant", "QAR 1,200", "QAR 9,000")
    for profile in content.list_clients():
        private_profile, private_needs = content.get_private_client(profile.id)
        assert profile == content.get_client(profile.id) == private_profile
        assert type(profile) is ClientProfile
        assert set(profile.model_dump()) == {
            "id", "name", "age", "occupation", "background",
            "public_financial_situation", "interview_opening_context",
        }
        public_json = profile.model_dump_json()
        for fact in (*private_needs.private_financial_facts, *private_markers):
            assert fact not in public_json

    for product in content.list_products():
        assert content.get_product(product.id) == product
        assert "hidden_needs" not in product.model_dump()


def test_invalid_json_reports_path_and_location(editable_data):
    (editable_data / "clients" / "maryam.json").write_text('{"id": }', encoding="utf-8")
    with pytest.raises(ContentLoadError, match=r"maryam\.json: invalid JSON at line 1, column \d+"):
        ContentService(editable_data)


@pytest.mark.parametrize(
    ("relative_path", "field"),
    [("clients/maryam.json", "id"), ("hidden_needs/maryam.json", "client_id"), ("products.json", "id")],
)
def test_missing_identifier_is_rejected(editable_data, relative_path, field):
    path = editable_data / relative_path
    payload = _read_json(path)
    record = payload[0] if isinstance(payload, list) else payload
    del record[field]
    _write_json(path, payload)
    with pytest.raises(ContentLoadError, match=f"{field}: Field required"):
        ContentService(editable_data)


@pytest.mark.parametrize("relative_path", ["clients/maryam.json", "hidden_needs/maryam.json", "products.json"])
def test_duplicate_identifiers_are_rejected(editable_data, relative_path):
    path = editable_data / relative_path
    payload = _read_json(path)
    if isinstance(payload, list):
        payload.append(payload[0])
        _write_json(path, payload)
    else:
        _write_json(path.with_name("duplicate-maryam.json"), payload)
    with pytest.raises(ContentLoadError, match="duplicate ID"):
        ContentService(editable_data)


def test_missing_private_profile_is_rejected(editable_data):
    (editable_data / "hidden_needs" / "mohamed.json").unlink()
    with pytest.raises(ContentLoadError, match="missing private profiles for: mohamed"):
        ContentService(editable_data)


def test_unknown_private_client_references_are_rejected(editable_data):
    path = editable_data / "hidden_needs" / "mohamed.json"
    payload = _read_json(path)
    payload["client_id"] = "unknown-client"
    _write_json(path, payload)
    with pytest.raises(ContentLoadError, match="unknown client IDs: unknown-client"):
        ContentService(editable_data)


def test_unknown_private_product_references_are_rejected(editable_data):
    path = editable_data / "hidden_needs" / "mohamed.json"
    payload = _read_json(path)
    payload["discovery_expectations"][0]["related_product_ids"] = ["unknown-product"]
    _write_json(path, payload)
    with pytest.raises(ContentLoadError, match="client 'mohamed' references unknown product ID 'unknown-product'"):
        ContentService(editable_data)


def test_public_schema_rejects_private_fields_and_invalid_values(editable_data):
    path = editable_data / "clients" / "maryam.json"
    payload = _read_json(path)
    payload.update(age="39", occupation=" ", private_financial_facts=["Private information"])
    _write_json(path, payload)

    with pytest.raises(ContentLoadError) as error:
        ContentService(editable_data)
    assert "age:" in str(error.value)
    assert "occupation:" in str(error.value)
    assert "private_financial_facts: Extra inputs are not permitted" in str(error.value)
    assert "Private information" not in str(error.value)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
