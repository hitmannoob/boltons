import importlib
import sys

import pytest

import boltons.queueutils as queueutils
from boltons.queueutils import (
    BasePriorityQueue, HeapPriorityQueue, PriorityQueue, SortedPriorityQueue)


def _test_priority_queue(queue_type):
    pq = queue_type()
    item1 = 'a'
    item2 = 'b'
    item3 = 'c'
    pq.add(item1)
    pq.remove(item1)

    # integer priorities
    pq.add(item1, 2)
    pq.add(item2, 9)
    pq.add(item3, 7)
    assert len(pq) == 3
    assert item2 == pq.pop()
    assert len(pq) == 2
    assert item3 == pq.pop()
    assert len(pq) == 1
    assert item1 == pq.pop()
    assert len(pq) == 0

    # float priorities
    pq.add(item1, 0.2)
    pq.add(item2, 0.9)
    pq.add(item3, 0.7)
    assert len(pq) == 3
    assert item2 == pq.pop()
    assert len(pq) == 2
    assert item3 == pq.pop()
    assert len(pq) == 1
    assert item1 == pq.pop()
    assert len(pq) == 0

    try:
        pq.pop()
    except IndexError:
        pass
    else:
        assert False, 'priority queue should be empty'
    return


def test_heap_queue():
    _test_priority_queue(HeapPriorityQueue)


def test_sorted_queue():
    _test_priority_queue(SortedPriorityQueue)


def test_priority_queue_alias():
    assert PriorityQueue is SortedPriorityQueue


@pytest.mark.parametrize('queue_type', [HeapPriorityQueue, SortedPriorityQueue])
def test_peek_does_not_remove(queue_type):
    pq = queue_type()
    pq.add('first', 3)
    pq.add('second', 2)
    assert pq.peek() == 'first'
    assert len(pq) == 2
    assert pq.pop() == 'first'
    assert pq.peek() == 'second'


@pytest.mark.parametrize('queue_type', [HeapPriorityQueue, SortedPriorityQueue])
def test_peek_and_pop_default_on_empty(queue_type):
    pq = queue_type()
    assert pq.peek(default=None) is None
    assert pq.pop(default='empty') == 'empty'
    assert len(pq) == 0


@pytest.mark.parametrize('queue_type', [HeapPriorityQueue, SortedPriorityQueue])
def test_peek_and_pop_raise_on_empty(queue_type):
    pq = queue_type()
    with pytest.raises(IndexError, match='peek on empty queue'):
        pq.peek()
    with pytest.raises(IndexError, match='pop on empty queue'):
        pq.pop()


@pytest.mark.parametrize('queue_type', [HeapPriorityQueue, SortedPriorityQueue])
def test_readding_changes_priority(queue_type):
    pq = queue_type()
    pq.add('task', 1)
    pq.add('other', 2)
    # Re-adding the same task replaces its entry and its priority.
    pq.add('task', 9)
    assert len(pq) == 2
    assert pq.pop() == 'task'
    assert pq.pop() == 'other'
    assert len(pq) == 0


@pytest.mark.parametrize('queue_type', [HeapPriorityQueue, SortedPriorityQueue])
def test_remove_absent_raises_keyerror(queue_type):
    pq = queue_type()
    pq.add('present')
    with pytest.raises(KeyError):
        pq.remove('absent')
    assert pq.pop() == 'present'


@pytest.mark.parametrize('queue_type', [HeapPriorityQueue, SortedPriorityQueue])
def test_removed_entry_is_culled(queue_type):
    pq = queue_type()
    pq.add('a', 1)
    pq.add('b', 2)
    pq.remove('b')
    # 'b' still sits in the backend but must never be returned.
    assert len(pq) == 1
    assert pq.peek() == 'a'
    assert pq.pop() == 'a'
    assert pq.pop(default=None) is None


@pytest.mark.parametrize('queue_type', [HeapPriorityQueue, SortedPriorityQueue])
def test_default_priority_is_zero(queue_type):
    pq = queue_type()
    pq.add('zero')
    pq.add('positive', 1)
    pq.add('negative', -1)
    assert pq.pop() == 'positive'
    assert pq.pop() == 'zero'
    assert pq.pop() == 'negative'


@pytest.mark.parametrize('queue_type', [HeapPriorityQueue, SortedPriorityQueue])
def test_custom_priority_key(queue_type):
    # With an identity priority_key, the *lowest* value is popped first.
    pq = queue_type(priority_key=lambda p: p)
    pq.add('a', 5)
    pq.add('b', 1)
    pq.add('c', 3)
    assert [pq.pop(), pq.pop(), pq.pop()] == ['b', 'c', 'a']


def test_unexpected_kwargs_raise_typeerror():
    with pytest.raises(TypeError, match='unexpected keyword arguments'):
        HeapPriorityQueue(bogus=True)


def test_base_queue_abstract_entry_methods_are_noops():
    assert BasePriorityQueue._push_entry([], [0, 0, 'x']) is None
    assert BasePriorityQueue._pop_entry([]) is None


def test_base_queue_subclass_contract():
    class ListPriorityQueue(BasePriorityQueue):
        @staticmethod
        def _push_entry(backend, entry):
            backend.append(entry)
            backend.sort()

        @staticmethod
        def _pop_entry(backend):
            return backend.pop(0)

    pq = ListPriorityQueue()
    pq.add('low', 0)
    pq.add('high', 10)
    assert isinstance(pq._pq, list)
    assert len(pq) == 2
    assert pq.pop() == 'high'
    assert pq.pop() == 'low'


def test_import_fallbacks_when_dependencies_missing(monkeypatch):
    # Reloading with the sibling modules blocked exercises the ImportError
    # fallbacks: a plain sentinel object and the builtin list backend.
    try:
        monkeypatch.setitem(sys.modules, 'boltons.typeutils', None)
        monkeypatch.setitem(sys.modules, 'boltons.listutils', None)
        reloaded = importlib.reload(queueutils)
        assert reloaded.SortedPriorityQueue._backend_type is list
        assert type(reloaded._REMOVED) is object
        pq = reloaded.SortedPriorityQueue()
        pq.add('task', 1)
        assert pq.pop() == 'task'
    finally:
        monkeypatch.undo()
        importlib.reload(queueutils)


def test_import_uses_sibling_modules():
    assert SortedPriorityQueue._backend_type is not list
    assert SortedPriorityQueue().pop(default=None) is None
