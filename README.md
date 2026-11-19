# Лабораторна робота №6 — Замикання та декоратори як HOF

**Варіант 3. Кеш каталогу товарів.** Іщенко Стефанія, ФеП-22.

Обов'язкові компоненти: closure для цінової політики, `@cached(ttl)`, `@timed`.
Кешується отримання товару; при зміні ціни кеш скидається **лише для цього `product_id`**.

## Структура
- `closures.py`
  - `make_counter` — стан через `nonlocal`;
  - `make_logger(prefix, sink)` — куди писати передається як залежність;
  - `make_price_policy(discount=, vat=)` — **цінова політика-замикання**;
  - `make_price_book(prices)` — сховище цін у замиканні (`get_base`, `set_base` з `nonlocal`).
- `decorators.py`
  - `@timed(label, unit=, logger=, clock=)` — час, лог навіть при винятку (`finally`);
  - `@cached(ttl=, time_fn=, logger=)` — TTL-кеш з `cache_clear()`, `cache_invalidate(predicate)`, `hits/misses`, `threading.Lock`;
  - `@count_calls(counter)` — лічильник реальних викликів;
  - усюди `functools.wraps` / `update_wrapper`, типи `ParamSpec` + `TypeVar`.
- `catalog.py` — `Catalog`: `get_product = timed(cached(fetch_product))`, `change_price(id, price)` → точкова інвалідація.
- `main.py` — демо.

## Порядок декораторів
`timed(cached(fetch))`: кеш усередині, таймер зовні — таймер міряє кожен виклик, у т.ч.
кеш-хіти (видно, що вони швидші). Якби навпаки — таймер спрацьовував би лише на промахах.

## Тести (`tests/test_lab6.py`, 14 шт.) — без реального часу та `sleep`
- стан замикань (`make_counter`, `make_price_book` не мутує джерело);
- `timed` з фейковим `clock` (рівно `12.345 ms`) і лог при винятку;
- збереження `__name__`, `__doc__`, `__wrapped__` у всіх декораторів;
- TTL на межі (`0.999` — ще живий, `+0.002` — протух) через `FakeTime`;
- ключ кешу враховує kwargs; `cache_invalidate` за предикатом; `cache_clear`;
- каталог: кешування, інвалідація лише зміненого товару, протухання TTL, невідомий товар.

## Запуск
```bash
pip install -r requirements.txt
pytest -q
mypy . && black --check . && ruff check .
python main.py
```
