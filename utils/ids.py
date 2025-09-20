import itertools


_id_counter = itertools.count(1)
def next_id(prefix: str) -> str:
    return f"{prefix}_{next(_id_counter)}"