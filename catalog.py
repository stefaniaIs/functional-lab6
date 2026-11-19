"""Каталог товарів: отримання товару з кешем; інвалідація при зміні ціни."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypedDict

from closures import PricePolicy, make_price_book
from decorators import Clock, Logger, cached, timed


class Product(TypedDict):
    id: int
    name: str
    base_price: float
    price: float


class Catalog:
    """Збирає все разом: «повільне сховище» + декоровані функції + інвалідація."""

    def __init__(
        self,
        names: dict[int, str],
        prices: dict[int, float],
        *,
        policy: PricePolicy,
        ttl: float = 60.0,
        time_fn: Clock = time.time,
        clock: Clock = time.perf_counter,
        logger: Logger = print,
        on_fetch: Callable[[int], None] = lambda _: None,
    ) -> None:
        self._names = dict(names)
        self._get_base, self._set_base = make_price_book(prices)

        def fetch_product(product_id: int) -> Product:
            """Повертає товар з ціною за поточною політикою (дорога операція)."""
            on_fetch(product_id)  # імітація звернення до БД
            base = self._get_base(product_id)
            return {
                "id": product_id,
                "name": self._names[product_id],
                "base_price": base,
                "price": policy(base),
            }

        # порядок: спершу кеш, зверху таймер (таймер міряє і кеш-хіти)
        self._cache = cached(ttl=ttl, time_fn=time_fn, logger=logger)(fetch_product)
        self.get_product = timed("get_product", logger=logger, clock=clock)(self._cache)

    def change_price(self, product_id: int, new_base: float) -> int:
        """Змінює ціну і скидає кеш лише для цього product_id."""
        self._set_base(product_id, new_base)
        return self._cache.cache_invalidate(lambda a, kw: a == (product_id,))

    def clear(self) -> None:
        self._cache.cache_clear()

    @property
    def stats(self) -> tuple[int, int]:
        return self._cache.hits, self._cache.misses
