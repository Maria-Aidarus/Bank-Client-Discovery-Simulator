"""Read and cross-check the editable JSON content."""

import json
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Annotated, TypeVar

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from .models import BankingProduct, ClientProfile, HiddenNeeds


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PACKAGED_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DATA_DIR = _PACKAGED_DATA_DIR if _PACKAGED_DATA_DIR.is_dir() else PROJECT_ROOT / "data"

_Record = TypeVar("_Record", bound=BaseModel)
_Result = TypeVar("_Result")
_ProductList = Annotated[list[BankingProduct], Field(min_length=1)]


class ContentLoadError(ValueError):
    """A content file is missing, unreadable, or invalid."""


def _read_json(path: Path, adapter: TypeAdapter[_Result]) -> _Result:
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContentLoadError(f"{path}: could not read JSON ({exc.strerror})") from exc
    except UnicodeError as exc:
        raise ContentLoadError(f"{path}: expected UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise ContentLoadError(
            f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno} ({exc.msg})"
        ) from exc

    try:
        return adapter.validate_python(raw_data)
    except ValidationError as exc:
        errors = exc.errors(include_input=False, include_url=False, include_context=False)
        details = "; ".join(
            f"{'.'.join(map(str, error['loc'])) or '<root>'}: {error['msg']}"
            for error in errors
        )
        raise ContentLoadError(f"{path}: {details}") from None


def _check_unique_ids(entries: Iterable[tuple[str, Path]]) -> None:
    seen: dict[str, Path] = {}
    for identifier, path in entries:
        if identifier in seen:
            raise ContentLoadError(f"{path}: duplicate ID '{identifier}' (also in {seen[identifier]})")
        seen[identifier] = path


class DataLoader:
    """Load content from the project or an explicitly supplied data directory."""

    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR) -> None:
        self.data_dir = data_dir.resolve()

    def load_clients(self) -> tuple[ClientProfile, ...]:
        clients = self._load_records("clients", ClientProfile, lambda client: client.id)
        if not clients:
            raise ContentLoadError(f"{self.data_dir / 'clients'}: no client JSON files found")
        return clients

    def load_hidden_needs(
        self, clients: Sequence[ClientProfile], products: Sequence[BankingProduct]
    ) -> tuple[HiddenNeeds, ...]:
        """Load private records and verify their client and product references."""
        records = self._load_records("hidden_needs", HiddenNeeds, lambda needs: needs.client_id)
        directory = self.data_dir / "hidden_needs"
        public_ids = {client.id for client in clients}
        private_ids = {record.client_id for record in records}
        if unknown_clients := private_ids - public_ids:
            raise ContentLoadError(
                f"{directory}: unknown client IDs: {', '.join(sorted(unknown_clients))}"
            )
        if missing_clients := public_ids - private_ids:
            raise ContentLoadError(
                f"{directory}: missing private profiles for: {', '.join(sorted(missing_clients))}"
            )

        product_ids = {product.id for product in products}
        for record in records:
            reference_groups = [topic.product_ids for topic in record.disclosure_topics]
            reference_groups.extend(expectation.related_product_ids for expectation in record.discovery_expectations)
            for references in reference_groups:
                for product_id in references:
                    if product_id not in product_ids:
                        raise ContentLoadError(
                            f"{directory}: client '{record.client_id}' references "
                            f"unknown product ID '{product_id}'"
                        )
        return records

    def load_products(self) -> tuple[BankingProduct, ...]:
        path = self.data_dir / "products.json"
        products = _read_json(path, TypeAdapter(_ProductList))
        _check_unique_ids((product.id, path) for product in products)
        return tuple(products)

    def _load_records(
        self, folder: str, model: type[_Record], get_id: Callable[[_Record], str]
    ) -> tuple[_Record, ...]:
        directory = self.data_dir / folder
        paths = sorted(directory.glob("*.json"))
        adapter = TypeAdapter(model)
        records = tuple(_read_json(path, adapter) for path in paths)
        _check_unique_ids((get_id(record), path) for record, path in zip(records, paths))
        return records
