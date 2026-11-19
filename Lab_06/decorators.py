"""Параметризовані декоратори: @timed, @cached(ttl) з інвалідацією, @count_calls."""

from __future__ import annotations

import functools
import threading
import time
from collections.abc import Callable, Hashable
from typing import Any, Generic, Literal, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

Logger = Callable[[str], None]
Clock = Callable[[], float]


def _noop(_: str) -> None:
    return None


def timed(
    label: str | None = None,
    *,
    unit: Literal["s", "ms", "us"] = "ms",
    logger: Logger = print,
    clock: Clock = time.perf_counter,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Логує час виконання (навіть якщо функція кинула виняток)."""
    factor = {"s": 1.0, "ms": 1e3, "us": 1e6}[unit]

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        name = label or func.__name__

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            t0 = clock()
            try:
                return func(*args, **kwargs)
            finally:
                logger(f"[timed] {name} took {(clock() - t0) * factor:.3f} {unit}")

        return wrapper

    return decorator


def make_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Hashable:
    return (args, tuple(sorted(kwargs.items())))


class CachedFunction(Generic[P, R]):
    """Обгортка-кеш: викликається як функція + має методи інвалідації."""

    def __init__(
        self,
        func: Callable[P, R],
        ttl: float | None,
        time_fn: Clock,
        logger: Logger,
    ) -> None:
        functools.update_wrapper(self, func)
        self.__wrapped__ = func
        self._func = func
        self._ttl = ttl
        self._time = time_fn
        self._log = logger
        self._cache: dict[Hashable, tuple[float | None, R]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        key = make_key(args, kwargs)
        now = self._time()
        with self._lock:
            if key in self._cache:
                exp, val = self._cache[key]
                if exp is None or now < exp:
                    self.hits += 1
                    self._log(f"[cached] hit {args}")
                    return val
                del self._cache[key]
                self._log(f"[cached] expired {args}")
            self.misses += 1
        val = self._func(*args, **kwargs)
        with self._lock:
            expiry = None if self._ttl is None else now + self._ttl
            self._cache[key] = (expiry, val)
        return val

    def cache_clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def cache_invalidate(
        self, predicate: Callable[[tuple[Any, ...], dict[str, Any]], bool]
    ) -> int:
        """Видаляє записи, для яких predicate(args, kwargs) істинний."""
        with self._lock:
            doomed = [
                k
                for k in self._cache
                if predicate(k[0], dict(k[1]))  # type: ignore[index]
            ]
            for k in doomed:
                del self._cache[k]
        return len(doomed)

    def cache_size(self) -> int:
        return len(self._cache)


def cached(
    *,
    ttl: float | None = None,
    time_fn: Clock = time.time,
    logger: Logger = _noop,
) -> Callable[[Callable[P, R]], CachedFunction[P, R]]:
    """Кеш з TTL; ttl=None - безстроково."""
    if ttl is not None and ttl <= 0:
        raise ValueError("ttl must be positive")

    def decorator(func: Callable[P, R]) -> CachedFunction[P, R]:
        return CachedFunction(func, ttl, time_fn, logger)

    return decorator


def count_calls(
    counter: Callable[[], int],
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Рахує справжні виклики функції через ін'єктований лічильник-замикання."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            counter()
            return func(*args, **kwargs)

        return wrapper

    return decorator
