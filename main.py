from catalog import Catalog
from closures import make_counter, make_logger, make_price_policy


def main() -> None:
    log = make_logger("catalog", print)
    fetches = make_counter()

    def on_fetch(_: int) -> None:
        print(f"  (звернення до сховища №{fetches()})")

    cat = Catalog(
        {1: "Ноутбук", 2: "Мишка"},
        {1: 30000.0, 2: 500.0},
        policy=make_price_policy(discount=0.1, vat=0.2),
        ttl=30,
        logger=log,
        on_fetch=on_fetch,
    )
    print(cat.get_product(1))
    print(cat.get_product(1))  # з кешу
    print(cat.get_product(2))
    print("Інвалідовано записів:", cat.change_price(1, 25000.0))
    print(cat.get_product(1))  # нова ціна
    print("hits/misses:", cat.stats)


if __name__ == "__main__":
    main()
