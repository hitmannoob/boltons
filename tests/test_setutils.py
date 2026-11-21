import itertools
import operator

from pytest import mark, raises

from boltons.setutils import IndexedSet, _MISSING, complement


def test_indexed_set_basic():
    zero2nine = IndexedSet(range(10))
    five2nine = zero2nine & IndexedSet(range(5, 15))
    x = IndexedSet(five2nine)
    x |= {10}

    assert list(zero2nine) == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert set(zero2nine) == {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}
    assert list(five2nine) == [5, 6, 7, 8, 9]
    assert x == IndexedSet([5, 6, 7, 8, 9, 10])
    assert x[-1] == 10

    assert zero2nine ^ five2nine == IndexedSet([0, 1, 2, 3, 4])

    assert x[:3] == IndexedSet([5, 6, 7])
    assert x[2:4:-1] == IndexedSet([8, 7])


def test_indexed_set_rsub():
    "From #252"
    assert (set('abc') - IndexedSet('bcd')) == {'a'}
    assert (IndexedSet('abc') - IndexedSet('bcd')) == IndexedSet(['a'])
    assert (frozenset('abc') - IndexedSet('bcd')) == frozenset(['a'])


@mark.parametrize('iterable_type', [list, tuple, iter])
def test_indexed_set_update_multiple_iterables(iterable_type):
    items = IndexedSet([1])

    result = items.update(iterable_type([2, 1, 3]), iterable_type([]),
                          iterable_type([3, 4, 2]))

    assert result is None
    assert list(items) == [1, 2, 3, 4]


def test_indexed_set_update_multiple_iterables_with_tuple_items():
    items = IndexedSet()

    items.update([(1, 2)], [(3, 4), (1, 2)])

    assert list(items) == [(1, 2), (3, 4)]


def test_indexed_set_mutate():
    thou = IndexedSet(range(1000))
    assert (thou.pop(), thou.pop()) == (999, 998)
    assert (thou.pop(499), thou.pop(499)) == (499, 500)

    ref = [495, 496, 497, 498, 501, 502, 503, 504, 505, 506]
    assert [thou[i] for i in range(495, 505)] == ref

    assert len(thou) == 996
    while len(thou) > 600:
        dead_idx_len = len(thou.dead_indices)
        dead_idx_count = thou._dead_index_count
        thou.pop(0)
        new_dead_idx_len = len(thou.dead_indices)
        if new_dead_idx_len < dead_idx_len:
            assert dead_idx_count > 0
            # 124, 109, 95
    assert len(thou) == 600
    assert thou._dead_index_count == 67

    assert not any([thou[i] is _MISSING for i in range(len(thou))])

    thou &= IndexedSet(range(500, 503))

    assert thou == IndexedSet([501, 502])
    return


def big_popper():
    # more of a benchmark than a test
    from os import urandom
    import time
    big_set = IndexedSet(range(100000))
    rands = [ord(r) for r in urandom(len(big_set))]
    start_time, start_size = time.time(), len(big_set)
    while len(big_set) > 10000:
        if len(big_set) % 10000 == 0:
            print(len(big_set) / 10000)
        rand = rands.pop()
        big_set.pop(rand)
        big_set.pop(-rand)
    end_time, end_size = time.time(), len(big_set)
    print()
    print('popped {} items in {} seconds'.format(start_size - end_size,
                                             end_time - start_time))


def test_complement_set():
    '''exercises a bunch of code-paths but doesn't really confirm math identities'''
    assert complement(complement(set())) == set()
    sab = set('ab')
    sbc = set('bc')
    cab = complement('ab')
    cbc = complement('bc')
    cc = complement('c')
    sc = set('c')
    u = complement(set())
    assert repr(sab) in repr(cab)
    # non-mutating tests
    assert cab != cbc
    assert complement(cab) == sab
    assert complement(cbc) == sbc
    assert 'a' not in cab
    assert 'c' in cab
    assert (sab & cbc) == (sab - sbc)  # set theory invariant
    assert not (cab < sab)  # complement never subset of set
    assert not (sab < cab)
    assert not (cbc < sab)
    assert not (cbc < cab)  # not subsets of each other
    assert sab < cc
    assert cab < (cab | cbc)
    assert (cab | cbc) > cab
    assert cc > sab
    assert not (cab > sab)
    # <= / >= between two complement sets (comp(X) <= comp(Y) iff Y subset X)
    assert cab <= complement('a')
    assert not (complement('a') <= cab)
    assert cab <= cab
    assert complement('a') >= cab
    assert cab >= cab
    # double-complemented (included-form) sets dispatch to the + +
    # branches of __le__/__ge__: comp(comp(X)) behaves like X
    ccab = complement(complement(set('ab')))
    cca = complement(complement(set('a')))
    assert ccab >= cca
    assert not (cca >= ccab)
    assert cca <= ccab
    assert not (ccab <= cca)
    assert ccab >= ccab
    assert ccab <= ccab
    assert not cab.isdisjoint(cc)  # complements never disjoint
    assert cab.isdisjoint(sab)
    assert not cab.isdisjoint(sc)
    assert (cab | sab) == u
    assert (cab | cc) == u
    assert (cab | cbc) == complement('b')
    assert (sab | cab) == (cbc | sbc)
    assert (sab & cab) == (cbc & sbc)
    assert (sab ^ cab) == (cbc ^ sbc)
    assert cab - cc == sc
    assert cab - sab == cab
    assert sab - cab == sab
    assert (cab ^ cbc | set('b')) == (sab | sbc)
    everything = complement(frozenset())
    assert everything in everything  # https://en.wikipedia.org/wiki/Russell%27s_paradox
    assert bool(cab)
    assert not complement(u)
    # destructive testing
    cab ^= sab
    cab ^= sab
    cab &= sab
    cab &= cbc
    cab |= sab
    cab |= cbc
    cab -= sab
    cab.add(5)
    cab.remove(5)
    cab.update(sab)
    cab.discard(sab)
    cab.update(cbc)
    cab.add(complement(frozenset()))  # frozen complement can be a member of complement set
    assert len({complement(frozenset()): 1, complement(frozenset()): 2}) == 1  # hash works
    with raises(NotImplementedError): cab.pop()
    with raises(NotImplementedError): len(cab)
    with raises(NotImplementedError): iter(cab)
    ~cab
    cab.complement()
    cab.complemented()
    class OpOverloader:
        # tests that operators properly return NotImplemented so they will defer to
        # another class implementation if available
        def __and__(self, other): return self
        __rand__ = __iand__ = __or__ = __ror__ = __ior__ = __xor__ = __rxor__ = __sub__ = __isub__ = __and__
        def __le__(self, other): return True
        __lt__ = __ge__ = __gt__ = __le__

    ops = OpOverloader()
    def opsmash(a, b):
        a &= b; a |= b; a -= b; a ^= b
        a > b; a >= b; a < b; a <= b
        return (((a & b) | b) - b) ^ b

    with raises(TypeError): opsmash(cab, object())
    assert opsmash(ops, cab) == ops
    assert opsmash(cab, ops) == ops


def test_iset_index_method():
    original_list = list(range(8, 20)) + list(range(8))

    indexed_list = IndexedSet()

    for i in original_list:
        indexed_list.add(i)

    for i in original_list:
        index = indexed_list.index(i)
        # if we're removing them in order, the target value should always be at index 0
        assert index == 0
        indexed_list.pop(index)

    indexed_list = IndexedSet(range(10))

    for i in reversed(range(10)):
        if i % 2:
            continue
        index = indexed_list.index(i)
        assert i == indexed_list.pop(index)


    indexed_list = IndexedSet(range(32))

    for i in list(indexed_list):
        if i % 3:
            index = indexed_list.index(i)
            assert i == indexed_list.pop(index)

    indexed_list = IndexedSet(range(10))

    for i in range(10):
        if i < 3:
            continue
        index = indexed_list.index(i)
        assert i == indexed_list.pop(index)

    indexed_list = IndexedSet(range(32))

    for i in list(indexed_list):
        if i % 3:
            index = indexed_list.index(i)
            assert i == indexed_list.pop(index)


def test_iset_slice_after_removal():
    # PR #423: slice bounds were mapped into item_list space while islice
    # consumed the apparent (dead-slot-free) stream, so any removal made
    # slices over-count.
    x = IndexedSet(range(10))
    x.pop(2)  # leaves [0, 1, 3, 4, 5, 6, 7, 8, 9] with a dead slot
    assert list(x[1:4]) == [1, 3, 4]
    assert list(x[-3:]) == [7, 8, 9]
    assert list(x[2:-1]) == [3, 4, 5, 6, 7, 8]
    assert isinstance(x[1:4], IndexedSet)


def test_iset_slice_agreement():
    # Slicing must not depend on dead slots: a set with removals must slice
    # identically to a freshly-built set with the same contents (all steps,
    # including the reversed-window negative-step semantics), and positive
    # steps must match list slicing exactly.
    bounds = (None, -12, -9, -5, -1, 0, 1, 4, 8, 9, 12)
    steps = (None, 1, 2, 3, -1, -2, -3)
    for pops in ([], [2], [0, 1, 2], [7, 8, 9], [0, 3, 6, 9], [1, 2, 5, 6]):
        iset = IndexedSet(range(10))
        for p in pops:
            iset.discard(p)
        fresh = IndexedSet(iset)  # same contents, no dead slots
        ref = list(iset)
        for start in bounds:
            for stop in bounds:
                for step in steps:
                    s = slice(start, stop, step)
                    assert list(iset[s]) == list(fresh[s]), (pops, s)
                    if step is None or step > 0:
                        assert list(iset[s]) == ref[s], (pops, s)


def test_iset_scalar_index_bounds():
    # Out-of-range negatives used to wrap silently: __getitem__ normalized
    # the index and _get_real_index normalized it AGAIN, so x[-10] on a
    # 9-element set returned x[-1], and pop(-15) removed a middle element.
    x = IndexedSet(range(10))
    x.pop(2)  # len 9, one dead slot
    assert x[-1] == 9
    assert x[-9] == 0
    with raises(IndexError):
        x[9]
    with raises(IndexError):
        x[-10]
    with raises(IndexError):
        x.pop(-15)
    assert 4 in x  # pop(-15) formerly silently removed 4
    with raises(IndexError):
        IndexedSet()[0]


def test_iset_scalar_index_multiple_dead_intervals():
    # exercise the _get_real_index interval walk across several dead ranges
    iset = IndexedSet(range(100))
    for p in (5, 20, 40, 60, 80):
        iset.discard(p)
    assert len(iset.dead_indices) == 5  # below compaction threshold (100/8)
    ref = list(iset)
    for i in list(range(-95, 95, 7)) + [0, -1, 94, -95]:
        assert iset[i] == ref[i]
    with raises(IndexError):
        iset[95]
    with raises(IndexError):
        iset[-96]


def test_bulk_difference_update():
    # removals large enough to take the O(n) bulk path (> _MAX_DEAD_INTERVALS)
    thing = IndexedSet(range(1000))
    thing.difference_update(set(range(0, 1000, 2)))
    assert list(thing) == list(range(1, 1000, 2))
    assert thing[0] == 1 and thing[-1] == 999
    assert thing.index(501) == 250
    thing.add(0)
    assert thing[-1] == 0


def test_bulk_intersection_update():
    thing = IndexedSet(range(1000))
    thing.intersection_update(set(range(500, 2000)))
    assert list(thing) == list(range(500, 1000))
    assert thing[0] == 500 and thing.index(750) == 250


def test_small_difference_update_unchanged():
    # small removals keep the incremental path
    thing = IndexedSet(range(100))
    thing.difference_update({1, 3, 5})
    assert list(thing)[:5] == [0, 2, 4, 6, 7]


def test_cull_trims_multiple_tail_intervals():
    # removing a tail out of order leaves unmerged dead intervals that
    # all have to go when the tail is trimmed
    iset = IndexedSet(range(39))
    for v in (0, 37, 36, 38):
        iset.remove(v)
    iset.add(39)
    assert iset.index(39) == 35
    assert iset[-1] == 39
    assert list(iset) == list(range(1, 36)) + [39]


def test_iset_pop_requires_int_index():
    # 3.0 == len - 1 used to take the pop-from-end fast path
    iset = IndexedSet(range(4))
    with raises(TypeError):
        iset.pop(3.0)
    assert list(iset) == [0, 1, 2, 3]


def test_iset_multi_arg_updates():
    iset = IndexedSet([1, 2, 3, 4])
    iset.difference_update({1, 2}, {2, 3})
    assert list(iset) == [4]
    iset = IndexedSet([1, 2, 3, 4])
    iset.intersection_update({1, 2}, {2, 3})
    assert list(iset) == [2]


def test_iset_iterator_operands():
    iset = IndexedSet([1, 2, 3, 4])
    assert list(iset.intersection(iter([2, 3, 5]))) == [2, 3]
    assert list(iset.difference(iter([2, 3, 5]))) == [1, 4]
    assert list(iset.symmetric_difference(iter([2, 3, 5]))) == [1, 4, 5]
    iset = IndexedSet([1, 2])
    iset ^= [2, 2, 5, 5]
    assert list(iset) == [1, 5]


_UNIVERSE = frozenset(range(6))
_SUBSETS = [set(), {0}, {1, 2}, {2, 3, 4}, set(range(6))]


def _make_cset(vals, rep):
    if rep == 'set':
        return set(vals)
    if rep == '+':
        return complement(complement(set(vals)))
    return complement(set(_UNIVERSE - vals))


@mark.parametrize('op, ref', [
    (operator.and_, operator.and_), (operator.iand, operator.and_),
    (operator.xor, operator.xor), (operator.ixor, operator.xor),
    (operator.or_, operator.or_), (operator.ior, operator.or_),
    (operator.sub, operator.sub), (operator.isub, operator.sub)])
def test_complement_set_identities(op, ref):
    # every representation pair must agree with plain set math, with
    # complement(x) materialized as (universe - x)
    reps = [('+', '+'), ('+', '-'), ('-', '+'), ('-', '-'),
            ('+', 'set'), ('-', 'set'), ('set', '+'), ('set', '-')]
    for a, b in itertools.product(_SUBSETS, repeat=2):
        for rep_a, rep_b in reps:
            res = op(_make_cset(a, rep_a), _make_cset(b, rep_b))
            got = {x for x in _UNIVERSE if x in res}
            assert got == ref(a, b), (op, a, rep_a, b, rep_b)


# --- coverage backfill: IndexedSet API surface ---

def test_iset_repr_and_eq():
    iset = IndexedSet([1, 2])
    assert repr(iset) == 'IndexedSet([1, 2])'
    assert iset == {2, 1}
    assert iset == [1, 2]
    assert not (iset == {1})
    assert iset != {1}
    assert not (iset == 1)  # non-iterable other falls through TypeError


def test_iset_remove_discard_clear():
    iset = IndexedSet([1, 2, 3])
    iset.remove(2)
    assert list(iset) == [1, 3]
    with raises(KeyError):
        iset.remove(2)
    iset.discard(2)  # quietly ignores a missing value
    iset.discard(1)
    assert list(iset) == [3]
    iset.clear()
    assert list(iset) == []
    assert len(iset) == 0
    assert iset.item_list == []


def test_iset_remove_only_item_culls():
    iset = IndexedSet([7])
    iset.remove(7)
    assert list(iset) == []
    assert iset.item_list == []
    assert iset.dead_indices == []


def test_iset_isdisjoint_subset_superset():
    a = IndexedSet([1, 2, 3])
    assert a.isdisjoint({4, 5})
    assert not a.isdisjoint({3, 4})
    assert a.issubset({1, 2, 3, 4})
    assert not a.issubset({1, 2})
    assert not a.issubset({1, 2, 4})
    assert a.issuperset({1, 2})
    assert not a.issuperset({1, 2, 4})


def test_iset_union_intersection_difference_multi():
    iset = IndexedSet([1, 2, 3, 4])
    assert list(iset.union([4, 5], (6,))) == [1, 2, 3, 4, 5, 6]
    assert list(iset.intersection({2, 3, 4}, [3, 4, 5])) == [3, 4]
    assert list(iset.iter_intersection({2, 3, 4}, [3, 4, 5])) == [3, 4]
    assert list(iset.difference({2}, [4])) == [1, 3]
    assert list(iset.iter_difference({2}, [4])) == [1, 3]


def test_iset_update_with_no_args():
    iset = IndexedSet([1])
    assert iset.update() is None
    assert list(iset) == [1]


def test_iset_symmetric_difference_update_self_clears():
    iset = IndexedSet([1, 2, 3])
    iset ^= iset
    assert list(iset) == []


def test_iset_count_reverse_sort_index():
    iset = IndexedSet([3, 1, 2])
    assert iset.count(1) == 1
    assert iset.count(9) == 0
    iset.reverse()
    assert list(iset) == [2, 1, 3]
    iset.sort()
    assert list(iset) == [1, 2, 3]
    iset.sort()  # already sorted -> early return
    assert list(iset) == [1, 2, 3]
    iset.sort(reverse=True)
    assert list(iset) == [3, 2, 1]
    iset.remove(2)
    assert iset.index(3) == 0
    assert iset.index(1) == 1
    with raises(ValueError):
        iset.index(2)


def test_iset_reverse_and_sort_drop_dead_slots():
    iset = IndexedSet(range(6))
    iset.remove(2)
    iset.remove(4)
    iset.reverse()
    assert list(iset) == [5, 3, 1, 0]
    iset.sort()
    assert list(iset) == [0, 1, 3, 5]
    assert iset.dead_indices == []


def test_iset_compact_noop_and_large():
    iset = IndexedSet(range(4))
    iset._compact()  # no dead indices -> early return
    assert list(iset) == [0, 1, 2, 3]

    big = IndexedSet(range(5000))
    for i in range(0, 5000, 10):  # 500 removals, past _MAX_DEAD_INTERVALS
        big.remove(i)
    assert len(big) == 4500
    assert big[0] == 1
    assert big._c_max_size > 0
    assert len(big.dead_indices) < 384


def test_iset_add_dead_merges_intervals():
    # a large set keeps the dead-slot intervals around (no compaction yet),
    # so adjacent removals exercise interval merging in _add_dead
    iset = IndexedSet(range(100))
    iset.remove(50)
    iset.remove(49)  # extend the interval leftward
    assert iset.dead_indices == [[49, 51]]
    iset.remove(51)  # extend the interval rightward
    assert iset.dead_indices == [[49, 52]]
    assert list(iset)[47:53] == [47, 48, 52, 53, 54, 55]


# --- coverage backfill: complement sets ---

def _materialize(obj, universe=_UNIVERSE):
    return {x for x in universe if x in obj}


def test_complement_named_binary_methods():
    reps = ['+', '-']
    for a, b in itertools.product(_SUBSETS, repeat=2):
        for rep_a, rep_b in itertools.product(reps, repeat=2):
            A, B = _make_cset(a, rep_a), _make_cset(b, rep_b)
            assert _materialize(A.intersection(B)) == a & b
            assert _materialize(A.union(B)) == a | b
            assert _materialize(A.difference(B)) == a - b
            assert _materialize(A.symmetric_difference(B)) == a ^ b


def test_complement_isdisjoint_and_subset_methods():
    # included-form complements act like finite sets
    a = _make_cset({1, 2}, '+')
    assert a.isdisjoint({3, 4})
    assert not a.isdisjoint({2, 3})
    assert a.issubset({1, 2, 3})
    assert not a.issubset({1, 4})
    assert a.issuperset({1})
    assert not a.issuperset({1, 4})
    # excluded-form complements are cofinite
    x = _make_cset({1, 2}, '-')
    y = _make_cset({3, 4}, '-')
    assert x.isdisjoint(y) is False  # cofinite sets always overlap
    assert x.isdisjoint(set()) is True  # nothing to overlap with
    assert x.isdisjoint(set(_UNIVERSE)) is False


def test_complement_named_methods_reject_bad_args():
    c = _make_cset({1, 2}, '-')
    for meth in (c.intersection, c.union, c.difference,
                 c.symmetric_difference, c.issubset, c.issuperset):
        with raises(TypeError):
            meth(object())


def test_complement_inplace_update_matches_union():
    # update() is union in place; it must agree with | for every
    # included/excluded representation pair (regression: three of the
    # four branches used to drop or invert the update)
    reps = ['+', '-']
    for a, b in itertools.product(_SUBSETS, repeat=2):
        for rep_a, rep_b in itertools.product(reps, repeat=2):
            A = _make_cset(a, rep_a)
            expected = _materialize(A | _make_cset(b, rep_b))
            A.update(_make_cset(b, rep_b))
            assert _materialize(A) == expected, ('update', a, rep_a, b, rep_b)


def test_complement_inplace_discard_matches_difference():
    # discard() is difference in place; it must agree with - for every
    # included/excluded representation pair (regression: included forms
    # silently ignored plain-set operands)
    reps = ['+', '-']
    for a, b in itertools.product(_SUBSETS, repeat=2):
        for rep_a, rep_b in itertools.product(reps, repeat=2):
            A = _make_cset(a, rep_a)
            expected = _materialize(A - _make_cset(b, rep_b))
            A.discard(_make_cset(b, rep_b))
            assert _materialize(A) == expected, ('discard', a, rep_a, b, rep_b)


def test_complement_update_discard_with_plain_iterables():
    # included (finite) form: materialization is exact
    inc = complement(complement({1, 2}))
    inc.update([3, 4])
    assert _materialize(inc) == {1, 2, 3, 4}
    inc.discard([1])
    assert _materialize(inc) == {2, 3, 4}

    # excluded (cofinite) form: excluded values are removed, not added
    exc = complement({1, 2})
    exc.update([1])
    assert _materialize(exc) == set(_UNIVERSE) - {2}
    exc.discard([3])
    assert _materialize(exc) == set(_UNIVERSE) - {2, 3}


def test_complement_symmetric_difference_update_all_reps():
    reps = ['+', '-']
    for a, b in itertools.product(_SUBSETS, repeat=2):
        for rep_a, rep_b in itertools.product(reps, repeat=2):
            A = _make_cset(a, rep_a)
            A.symmetric_difference_update(_make_cset(b, rep_b))
            assert _materialize(A) == (a ^ b), (a, rep_a, b, rep_b)


def test_complement_rsub_all_reps():
    for a, b in itertools.product(_SUBSETS, repeat=2):
        for rep_a, rep_b in itertools.product(['+', '-'], repeat=2):
            A, B = _make_cset(a, rep_a), _make_cset(b, rep_b)
            got = A - B
            assert _materialize(got) == (a - b)


def test_complement_complemented_roundtrip():
    s = set(range(4))
    c = complement(s)  # cofinite: everything but {0, 1, 2, 3}
    assert repr(c) == 'complement({0, 1, 2, 3})'
    inc = c.complemented()  # the finite included form
    assert inc._included == s and inc._excluded is None
    assert _materialize(inc) == s
    assert complement(inc) == c
    # frozenset-backed complements stay frozenset-backed
    fc = complement(frozenset({1, 2}))
    fcc = fc.complemented()
    assert fcc._included == frozenset({1, 2})
    assert isinstance(fcc._included, frozenset)


def test_complement_inplace_complement_and_mutation():
    c = complement({1, 2})  # cofinite, missing 1 and 2
    c.complement()  # flips to the finite included form {1, 2}
    assert _materialize(c) == {1, 2}
    c.complement()  # and back
    assert _materialize(c) == set(_UNIVERSE) - {1, 2}

    inc = complement(complement({1, 2}))
    popped = inc.pop()
    assert popped in {1, 2}
    inc.add(3)
    assert _materialize(inc) == ({1, 2} - {popped}) | {3}
    inc.remove(3)
    assert _materialize(inc) == {1, 2} - {popped}

    exc = complement({1})  # everything but 1
    exc.add(1)  # adding the missing element makes it universal
    assert _materialize(exc) == set(_UNIVERSE)
    exc.remove(1)  # removing it excludes it again
    assert _materialize(exc) == set(_UNIVERSE) - {1}


def test_complement_dunder_protocols():
    inc = complement(complement({1, 2}))
    exc = complement({1, 2})
    assert len(inc) == 2
    assert sorted(iter(inc)) == [1, 2]
    assert bool(inc) is True
    assert bool(complement(complement(set()))) is False
    assert bool(exc) is True
    with raises(NotImplementedError):
        len(exc)
    with raises(NotImplementedError):
        iter(exc)
    # hashing needs immutable (frozenset-backed) contents
    frozen = complement(frozenset({1, 2}))
    assert hash(frozen) == hash(frozen)
    assert frozen == complement(frozenset({1, 2}))
    assert inc == complement(complement({1, 2}))
    assert inc == {1, 2}
    assert inc != {1}
    with raises(ValueError):
        _ComplementSetBoth()


def _ComplementSetBoth():
    from boltons.setutils import _ComplementSet
    return _ComplementSet(included={1}, excluded={2})


def test_complement_operator_type_errors():
    c = complement({1, 2})
    for fn in (lambda: c & object(), lambda: c | object(),
               lambda: c ^ object(), lambda: c - object()):
        with raises(TypeError):
            fn()


def test_iset_issuperset_longer_other_and_isub():
    a = IndexedSet([1, 2, 3])
    assert not a.issuperset({1, 2, 3, 4})  # longer other -> early False
    a -= {2}
    assert list(a) == [1, 3]


def test_complement_repr_included_form():
    inc = complement(complement({1, 2}))
    assert repr(inc) == 'complement(complement({1, 2}))'
    assert repr(complement({1, 2})) == 'complement({1, 2})'


def test_complement_typeerror_normalization():
    c = complement({1, 2})
    with raises(TypeError):
        c.isdisjoint(object())
    with raises(TypeError):
        c.symmetric_difference_update(object())
    with raises(TypeError):
        c.difference_update(object())


def test_complement_isdisjoint_included_excluded():
    inc = complement(complement({1, 2}))
    assert not inc.isdisjoint(complement({2, 3}))  # share 2
    assert inc.isdisjoint(complement({1, 2}))  # both exclude 1 and 2


def test_complement_ordering_branches():
    exc = complement({1, 2})              # cofinite, missing {1, 2}
    inc = complement(complement({1, 2}))  # finite {1, 2}
    inc2 = complement(complement({1, 2, 3}))
    inc3 = complement(complement({1}))

    # excluded vs plain
    assert (exc <= {1}) is False
    assert (exc < {1}) is False
    assert (exc >= {1}) is False
    assert (exc > {1}) is False

    # included vs excluded
    assert (inc <= complement({2, 3})) is False
    assert (inc < complement({2, 3})) is False
    assert (inc >= complement({2, 3})) is False
    assert (inc > complement({2, 3})) is False

    # included vs plain and included vs included
    assert inc <= {1, 2, 3}
    assert inc < {1, 2, 3}
    assert inc2 >= inc
    assert inc2 > inc
    assert inc <= inc2
    assert inc < inc2
    assert not (inc < inc)
    assert inc <= inc
    assert inc3 <= inc
    assert not (inc3 >= inc)


def test_complement_inplace_dunders_defer():
    c = complement({1, 2})
    assert c.__ior__(object()) is NotImplemented
    assert c.__isub__(object()) is NotImplemented
    assert c.__rsub__(object()) is NotImplemented
    assert c.__lt__(object()) is NotImplemented
    assert c.__gt__(object()) is NotImplemented
