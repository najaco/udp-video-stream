from typing import List

from src.delta_list import DeltaList


def test_delta_insert():
    dlist: DeltaList[str] = DeltaList()
    items = [(2, "A"), (1, "B"), (8, "C")]
    for (k, e) in items:
        dlist.insert(k, e)
    dlist.print_list()
    assert dlist.size == 3

def test_delta_insert_2():
    dlist: DeltaList[str] = DeltaList()
    items = [(40, "A"), (20, "B"), (83, "C"), (40, "D"), (60, "E"), (2, "F"), (10, "G")]
    correct_order = ["F", "G", "B", "A", "D", "E", "C"]
    for (k, e) in items:
        dlist.insert(k, e)
    l = dlist.to_list()
    print("State of DList: ", l)
    print("{0:12}{1}".format("Actual:", [x[1] for x in l]))
    print("{0:12}{1}".format("Expected:", correct_order))
    for (i, j) in zip(correct_order, l):
        assert i == j[1]



def test_delta_decrement_key():
    dlist: DeltaList[str] = DeltaList()
    items = [(2, "A"), (1, "B"), (4, "C")]
    for (k, e) in items:
        dlist.insert(k, e)
    dlist.decrement_key()
    ready: List[str] = dlist.remove_all_ready()
    assert len(ready) == 1
    assert dlist.size == 2
    assert ready[0] == "B"
    dlist.decrement_key()
    ready2: List[str] = dlist.remove_all_ready()
    assert len(ready2) == 1
    assert dlist.size == 1
    assert ready2[0] == "A"
    dlist.decrement_key()

    ready3: List[str] = dlist.remove_all_ready()
    assert len(ready3) == 0
    assert dlist.size == 1

    dlist.decrement_key()
    ready4: List[str] = dlist.remove_all_ready()
    assert len(ready4) == 1
    assert dlist.size == 0
    assert ready4[0] == "C"


def test_delta_remove_first():
    dlist: DeltaList[str] = DeltaList()
    items = [(40, "A"), (20, "B"), (83, "C"), (40, "D"), (60, "E"), (2, "F"), (10, "G")]
    for (k, e) in items:
        dlist.insert(k, e)
    e = dlist.remove_first()
    assert e == "F"
    items.sort(key=lambda x: x[0])
    items.pop(0)
    dlist_list = dlist.to_list()
    print("{0:12}{1}".format("Actual:", dlist_list))
    print("{0:12}{1}".format("Expected:", items))
    assert len(dlist_list) == len(items)
    for (i, j) in zip(dlist_list, items):
        assert i[1] == j[1]
    assert dlist_list[0][0] == items[0][0]


def test_delta_remove_first_empty_none():
    dlist: DeltaList[str] = DeltaList()
    assert dlist.remove_first() is None
