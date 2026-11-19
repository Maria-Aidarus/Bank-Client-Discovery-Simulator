"""Provide public catalogue views and explicit server-side private access."""

from pathlib import Path

from ..data_loader import DEFAULT_DATA_DIR, DataLoader
from ..models import BankingProduct, ClientProfile, HiddenNeeds


class ContentService:
    """A validated snapshot of the editable simulator content."""

    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR) -> None:
        loader = DataLoader(data_dir)
        clients = loader.load_clients()
        products = loader.load_products()
        hidden_needs = loader.load_hidden_needs(clients, products)
        self._clients = {client.id: client for client in clients}
        self._products = {product.id: product for product in products}
        self._hidden_needs = {needs.client_id: needs for needs in hidden_needs}

    def list_clients(self) -> tuple[ClientProfile, ...]:
        return tuple(self._clients.values())

    def get_client(self, client_id: str) -> ClientProfile:
        try:
            return self._clients[client_id]
        except KeyError:
            raise ValueError(f"Unknown client ID '{client_id}'.") from None

    def list_products(self) -> tuple[BankingProduct, ...]:
        return tuple(self._products.values())

    def get_product(self, product_id: str) -> BankingProduct:
        try:
            return self._products[product_id]
        except KeyError:
            raise ValueError(f"Unknown product ID '{product_id}'.") from None

    def get_private_client(self, client_id: str) -> tuple[ClientProfile, HiddenNeeds]:
        """Return the full client record for server-side agent context only."""
        return self.get_client(client_id), self._hidden_needs[client_id]
