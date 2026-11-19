"""Замикання для варіанту 3 (кеш каталогу товарів)."""

from __future__ import annotations

from collections.abc import Callable


def make_counter(start: int = 0) -> Callable[[], int]:
    """Лічильник викликів: стан value живе в замиканні (nonlocal)."""
    value = start

    def inc() -> int:
        nonlocal value
        value += 1
        return value

    return inc


def make_logger(prefix: str, sink: Callable[[str], None]) -> Callable[[str], None]:
    """Логер з префіксом; куди писати (print, список у тесті) - залежність."""

    def log(msg: str) -> None:
        sink(f"[{prefix}] {msg}")

    return log


PricePolicy = Callable[[float], float]


def make_price_policy(
    *, discount: float = 0.0, vat: float = 0.2, rounding: int = 2
) -> PricePolicy:
    """Цінова політика: параметри «заморожені» в замиканні."""
    if not 0 <= discount < 1:
        raise ValueError("discount must be in [0, 1)")

    def price(base: float) -> float:
        return round(base * (1 - discount) * (1 + vat), rounding)

    return price


def make_price_book(
    initial: dict[int, float],
) -> tuple[Callable[[int], float], Callable[[int, float], float]]:
    """Сховище базових цін у замиканні: (get_base, set_base).

    set_base повертає стару ціну. Стан змінюється лише через set_base.
    """
    prices = dict(initial)  # копія, назовні посилання немає

    def get_base(product_id: int) -> float:
        if product_id not in prices:
            raise KeyError(f"unknown product {product_id}")
        return prices[product_id]

    def set_base(product_id: int, value: float) -> float:
        nonlocal prices
        old = prices.get(product_id, 0.0)
        prices = {**prices, product_id: value}
        return old

    return get_base, set_base
