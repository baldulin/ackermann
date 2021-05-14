import logging
from asyncio import sleep

import pytest
from command.config import ConfigUnit
from command.exceptions import CycleException
from command.kahn import KahnIterator


class Node:
    def __init__(self, name, before, after, belongs):
        self.name = name
        self.before = before
        self.after = after
        self.belongs = belongs

    def __str__(self):
        return self.name
    __repr__ = __str__


def test_kahn_iterator():
    a = Node("a", before=[], after=[], belongs=[])
    b = Node("b", before=[a], after=[], belongs=[])
    c = Node("c", before=[a], after=[b], belongs=[])

    k = KahnIterator([a, b, c])
    i = iter(k)

    assert next(i) == b
    assert next(i) == c
    assert next(i) == a


def test_kahn_iterator_add_node():
    a = Node("a", before=[], after=[], belongs=[])
    b = Node("b", before=[a], after=[], belongs=[])
    c = Node("c", before=[a], after=[b], belongs=[])

    k = KahnIterator([a, b, c])
    i = iter(k)

    assert next(i) == b
    d = Node("d", before=[c], after=[], belongs=[])
    k.add_node(d)
    assert next(i) == d
    assert next(i) == c
    assert next(i) == a


def test_kahn_remove_node():
    a = Node("a", before=[], after=[], belongs=[])
    b = Node("b", before=[a], after=[], belongs=[])
    c = Node("c", before=[a], after=[b], belongs=[])

    k = KahnIterator([a, b, c])
    i = iter(k)

    assert next(i) == b
    k.remove_node(c)
    assert next(i) == a


def test_kahn_iterator_cycle():
    a = Node("a", before=[], after=[], belongs=[])
    b = Node("b", before=[a], after=[], belongs=[])
    c = Node("c", before=[b], after=[a], belongs=[])
    k = KahnIterator([a, b, c])
    i = iter(k)

    with pytest.raises(CycleException):
        next(i)
