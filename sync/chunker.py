from itertools import islice
from typing import Iterator, List, Any


def chunked(iterable: Iterator[Any], size: int = 1000) -> Iterator[List[Any]]:
    """Генератор пачек фиксированного размера из итератора."""
    while True:
        chunk = list(islice(iterable, size))
        if not chunk:
            break
        yield chunk
