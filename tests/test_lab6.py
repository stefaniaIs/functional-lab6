import pytest

from catalog import Catalog
from closures import make_counter, make_logger, make_price_book, make_price_policy
from decorators import cached, count_calls, timed


class FakeTime:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


# --- замикання ---------------------------------------------------------------
def test_counter_state() -> None:
    c1, c2 = make_counter(10), make_counter()
    assert (c1(), c1(), c2()) == (11, 12, 1)


def test_logger_injected_sink() -> None:
    logs: list[str] = []
    make_logger("X", logs.append)("hi")
    assert logs == ["[X] hi"]


def test_price_policy() -> None:
    assert make_price_policy(discount=0.1, vat=0.2)(100) == 108.0
    assert make_price_policy(vat=0)(99.999) == 100.0
    with pytest.raises(ValueError):
        make_price_policy(discount=1.5)


def test_price_book_closure() -> None:
    src = {1: 10.0}
    get, set_ = make_price_book(src)
    assert set_(1, 20.0) == 10.0
    assert get(1) == 20.0 and src == {1: 10.0}
    with pytest.raises(KeyError):
        get(99)


# --- timed -------------------------------------------------------------------
def test_timed_fake_clock() -> None:
    ticks = iter([0.0, 0.012345])
    logs: list[str] = []

    @timed("work", logger=logs.append, clock=lambda: next(ticks))
    def work(x: int) -> int:
        """doc"""
        return x * x

    assert work(5) == 25
    assert logs == ["[timed] work took 12.345 ms"]


def test_timed_logs_on_exception() -> None:
    logs: list[str] = []

    @timed(logger=logs.append, clock=FakeTime(), unit="s")
    def boom() -> None:
        raise RuntimeError

    with pytest.raises(RuntimeError):
        boom()
    assert logs == ["[timed] boom took 0.000 s"]


def test_wraps_metadata() -> None:
    def price(pid: int) -> float:
        """Повертає ціну."""
        return 1.0

    for deco in (timed(logger=lambda _: None), cached(), count_calls(make_counter())):
        w = deco(price)
        assert w.__name__ == "price"
        assert w.__doc__ == "Повертає ціну."
        assert getattr(w, "__wrapped__", None) is price


# --- cached ------------------------------------------------------------------
def test_cached_ttl_fake_time() -> None:
    now = FakeTime()
    calls = make_counter()

    @cached(ttl=1.0, time_fn=now)
    @count_calls(calls)
    def f(x: int) -> int:
        return x * 2

    assert f(10) == 20 and f(10) == 20
    assert (f.hits, f.misses) == (1, 1)
    now.t += 0.999
    f(10)
    assert f.misses == 1  # ще живий
    now.t += 0.002
    assert f(10) == 20
    assert f.misses == 2  # протух
    assert calls() == 3  # 2 реальні виклики + цей


def test_cached_kwargs_key_and_invalidate() -> None:
    @cached()
    def g(a: int, *, b: int = 0) -> int:
        return a + b

    g(1, b=2), g(1, b=3), g(2)
    assert g.cache_size() == 3
    assert g.cache_invalidate(lambda a, kw: a == (1,)) == 2
    assert g.cache_size() == 1
    g.cache_clear()
    assert g.cache_size() == 0


def test_cached_invalid_ttl() -> None:
    with pytest.raises(ValueError):
        cached(ttl=0)


# --- каталог (варіант 3) ------------------------------------------------------
def make_catalog(now: FakeTime, fetched: list[int], logs: list[str]) -> Catalog:
    return Catalog(
        {1: "Laptop", 2: "Mouse"},
        {1: 1000.0, 2: 50.0},
        policy=make_price_policy(discount=0.1, vat=0.2),
        ttl=60,
        time_fn=now,
        clock=FakeTime(0.0),
        logger=logs.append,
        on_fetch=fetched.append,
    )


def test_catalog_caches_products() -> None:
    fetched: list[int] = []
    cat = make_catalog(FakeTime(), fetched, [])
    p = cat.get_product(1)
    assert p == {"id": 1, "name": "Laptop", "base_price": 1000.0, "price": 1080.0}
    cat.get_product(1)
    cat.get_product(2)
    assert fetched == [1, 2]
    assert cat.stats == (1, 2)


def test_change_price_invalidates_only_that_product() -> None:
    fetched: list[int] = []
    cat = make_catalog(FakeTime(), fetched, [])
    cat.get_product(1), cat.get_product(2)
    assert cat.change_price(1, 500.0) == 1
    assert cat.get_product(1)["price"] == 540.0
    cat.get_product(2)
    assert fetched == [1, 2, 1]  # 2 узято з кешу


def test_catalog_ttl_expiry_and_timing_logs() -> None:
    now, fetched, logs = FakeTime(), [], []  # type: ignore[var-annotated]
    cat = make_catalog(now, fetched, logs)
    cat.get_product(2)
    now.t += 61
    cat.get_product(2)
    assert fetched == [2, 2]
    assert any(m.startswith("[timed] get_product") for m in logs)
    assert any("expired" in m for m in logs)
    cat.clear()
    cat.get_product(2)
    assert fetched == [2, 2, 2]


def test_unknown_product() -> None:
    cat = make_catalog(FakeTime(), [], [])
    with pytest.raises(KeyError):
        cat.get_product(42)
