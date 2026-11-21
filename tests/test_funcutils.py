import functools
import inspect
import threading
import time
import types

import pytest

from boltons.funcutils import (copy_function,
                               total_ordering,
                               format_invocation,
                               InstancePartial,
                               CachedInstancePartial,
                               noop,
                               once,
                               inspect_formatargspec,
                               get_module_callables,
                               mro_items,
                               dir_dict,
                               partial_ordering,
                               format_exp_repr,
                               format_nonexp_repr,
                               update_wrapper,
                               wraps,
                               FunctionBuilder,
                               MissingArgument,
                               ExistingArgument,
                               NO_DEFAULT)


class Greeter:
    def __init__(self, greeting):
        self.greeting = greeting

    def greet(self, excitement='.'):
        return self.greeting.capitalize() + excitement

    partial_greet = InstancePartial(greet, excitement='!')
    cached_partial_greet = CachedInstancePartial(greet, excitement='...')

    def native_greet(self):
        return self.greet(';')


class SubGreeter(Greeter):
    pass


def test_partials():
    g = SubGreeter('hello')

    assert g.greet() == 'Hello.'
    assert g.native_greet() == 'Hello;'
    assert g.partial_greet() == 'Hello!'
    assert g.cached_partial_greet() == 'Hello...'
    assert CachedInstancePartial(g.greet, excitement='s')() == 'Hellos'

    g.native_greet = 'native reassigned'
    assert g.native_greet == 'native reassigned'

    g.partial_greet = 'partial reassigned'
    assert g.partial_greet == 'partial reassigned'

    g.cached_partial_greet = 'cached_partial reassigned'
    assert g.cached_partial_greet == 'cached_partial reassigned'


def test_copy_function():
    def callee():
        return 1
    callee_copy = copy_function(callee)
    assert callee is not callee_copy
    assert callee() == callee_copy()


def test_total_ordering():
    @total_ordering
    class Number:
        def __init__(self, val):
            self.val = int(val)

        def __gt__(self, other):
            return self.val > other

        def __eq__(self, other):
            return self.val == other

    num = Number(3)
    assert num > 0
    assert num == 3

    assert num < 5
    assert num >= 2
    assert num != 1


def test_format_invocation():
    assert format_invocation('d') == "d()"
    assert format_invocation('f', ('a', 'b')) == "f('a', 'b')"
    assert format_invocation('g', (), {'x': 'y'})  == "g(x='y')"
    assert format_invocation('h', ('a', 'b'), {'x': 'y', 'z': 'zz'}) == "h('a', 'b', x='y', z='zz')"

def test_noop():
    assert noop() is None
    assert noop(1, 2) is None
    assert noop(a=1, b=2) is None


def test_once_executes_only_once():
    call_count = 0

    @once
    def get_value():
        nonlocal call_count
        call_count += 1
        return 42

    assert get_value() == 42
    assert get_value() == 42
    assert get_value() == 42
    assert call_count == 1


def test_once_caches_result():
    @once
    def get_list():
        return [1, 2, 3]

    result1 = get_list()
    result2 = get_list()
    assert result1 is result2


def test_once_thread_safety():
    call_count = 0
    barrier = threading.Barrier(10)

    @once
    def slow_computation():
        nonlocal call_count
        call_count += 1
        time.sleep(0.5)
        return 99

    results = []
    errors = []

    def worker():
        try:
            barrier.wait()
            results.append(slow_computation())
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert call_count == 1
    assert all(r == 99 for r in results)
    assert len(results) == 10


def test_inspect_formatargspec_annotations_defaults_and_returns():
    spec = inspect_formatargspec(
        ['a', 'b'], varargs='args', varkw='kwargs', defaults=(2,),
        kwonlyargs=['c'], kwonlydefaults={'c': 3},
        annotations={'a': int, 'return': str})
    assert spec == '(a: int, b=2, *args, c=3, **kwargs) -> str'

    assert inspect_formatargspec(['a'], annotations={'a': int}) == '(a: int)'
    assert inspect_formatargspec(['a'], annotations={'a': int},
                                 formatarg=str) == '(a: int)'


def test_inspect_formatargspec_star_and_posonly():
    # A bare keyword-only arg forces the '*' marker when there is no *args.
    assert inspect_formatargspec(
        ['a'], kwonlyargs=['b'], kwonlydefaults={'b': 5}) == '(a, *, b=5)'
    # Positional-only args get a '/' after the last one.
    assert inspect_formatargspec(
        ['a', 'b'], posonlyargs=['a']) == '(a, /, b)'


def test_get_module_callables():
    module = types.ModuleType('fake_mod')

    class FakeClass:
        pass

    def fake_func():
        pass

    a_module = types.ModuleType('other_mod')

    class ForeignClass:
        pass

    FakeClass.__module__ = 'fake_mod'
    fake_func.__module__ = 'fake_mod'
    module.FakeClass = FakeClass
    module.fake_func = fake_func
    module.foreign = ForeignClass
    module.foreign.__module__ = 'other_mod'
    module.not_a_module_attr = object()

    types_map, funcs_map = get_module_callables(module)
    assert types_map['FakeClass'] is FakeClass
    assert funcs_map['fake_func'] is fake_func
    assert 'ForeignClass' not in types_map
    assert 'not_a_module_attr' not in funcs_map

    filtered_types, filtered_funcs = get_module_callables(
        module, ignore=lambda name: name.lower().startswith('fake'))
    assert 'FakeClass' not in filtered_types
    assert 'fake_func' not in filtered_funcs


def test_get_module_callables_by_name():
    types_map, funcs_map = get_module_callables('boltons.funcutils')
    assert types_map['FunctionBuilder'] is FunctionBuilder
    assert funcs_map['noop'] is noop
    assert funcs_map['wraps'] is wraps


def test_mro_items_walks_bases():
    class Base:
        base_attr = 1

    class Child(Base):
        child_attr = 2

    items = dict(mro_items(Child))
    assert items['base_attr'] == 1
    assert items['child_attr'] == 2
    assert 'object' not in items


def test_dir_dict_includes_inherited_and_handles_raising_attrs():
    class Base:
        inherited = 'from-base'

    class Child(Base):
        def __init__(self):
            self.instance = 'from-instance'

    d = dir_dict(Child())
    assert d['instance'] == 'from-instance'
    assert d['inherited'] == 'from-base'
    assert d['__class__'] is Child

    class Raising:
        @property
        def boom(self):
            raise RuntimeError('nope')

    assert 'boom' not in dir_dict(Raising())
    with pytest.raises(RuntimeError):
        dir_dict(Raising(), raise_exc=True)


def test_partial_ordering_does_not_override_existing_methods():
    class HasComparisons:
        def __le__(self, other):
            return 'le'

        def __ge__(self, other):
            return 'ge'

        def __lt__(self, other):
            return 'custom-lt'

    decorated = partial_ordering(HasComparisons)
    assert decorated is HasComparisons
    assert (HasComparisons() < HasComparisons()) == 'custom-lt'


def test_instance_partial_exposes_partialmethod():
    class Greeter:
        def __init__(self, greeting):
            self.greeting = greeting

        def greet(self, excitement='.'):
            return self.greeting + excitement

        excite = InstancePartial(greet, excitement='!')

    g = Greeter('hi')
    assert g.excite() == 'hi!'
    descriptor = Greeter.__dict__['excite']
    assert isinstance(descriptor._partialmethod, functools.partialmethod)
    assert isinstance(descriptor.__partialmethod__, functools.partialmethod)


def test_cached_instance_partial_caches_bound_method():
    class Greeter:
        def __init__(self, greeting):
            self.greeting = greeting

        def greet(self, excitement='.'):
            return self.greeting + excitement

        excite = CachedInstancePartial(greet, excitement='?')

    g = Greeter('hi')
    first = g.excite
    assert first() == 'hi?'
    assert g.excite is first
    # Accessing through the class has no instance to bind to.
    with pytest.raises(TypeError):
        Greeter.__dict__['excite'].__get__(None, Greeter)


def test_cached_instance_partial_set_name_records_name():
    class Greeter:
        def greet(self):
            return 'hi'

        excite = CachedInstancePartial(greet)

    assert Greeter.__dict__['excite'].__name__ == 'excite'


def test_format_invocation_rejects_unknown_kwargs_and_accepts_pairs():
    with pytest.raises(TypeError):
        format_invocation('f', unknown=1)
    assert format_invocation(
        'f', args=(1,), kwargs=[('a', 1), ('b', 2)]) == 'f(1, a=1, b=2)'


def test_format_invocation_custom_repr():
    assert format_invocation('f', args=(1,), repr=lambda v: 'N') == 'f(N)'


def test_format_exp_repr():
    class Flag:
        def __init__(self, length, width, depth=None):
            self.length = length
            self.width = width
            self.depth = depth

    flag = Flag(5, 10)
    flag2 = Flag(5, 15, 2)
    assert format_exp_repr(flag, ['length', 'width'], [], ['depth']) == 'Flag(5, 10)'
    assert format_exp_repr(flag2, ['length'], ['width', 'depth']) == \
        'Flag(5, width=15, depth=2)'
    # A custom opt_key decides which optional names appear.
    assert format_exp_repr(flag, ['length'], ['width'], ['depth'],
                           opt_key=lambda v: not v) == 'Flag(5, width=10)'


def test_format_nonexp_repr():
    class Flag:
        def __init__(self, length, width, depth=None):
            self.length = length
            self.width = width
            self.depth = depth

    flag = Flag(5, 10)
    assert format_nonexp_repr(flag, ['length', 'width'], ['depth']) == \
        '<Flag length=5 width=10>'
    empty_repr = format_nonexp_repr(flag)
    assert empty_repr.startswith('<Flag id=')
    assert empty_repr.endswith('>')


def test_update_wrapper_expected_argument_forms():
    def base(a, b=2):
        return a + b

    def wrapper(*args, **kwargs):
        return args, kwargs

    as_name = update_wrapper(wrapper, base, expected='c')
    assert as_name(1, 2, 3) == ((1, 2), {'c': 3})

    as_pair = update_wrapper(wrapper, base, expected=[('c', 5)])
    assert as_pair(1) == ((1,), {'b': 2, 'c': 5})

    as_mapping = update_wrapper(wrapper, base, expected={'c': 3})
    assert as_mapping(1) == ((1,), {'b': 2, 'c': 3})

    as_kwonly = update_wrapper(wrapper, base, expected=[('z', 9, True)])
    assert as_kwonly(1) == ((1,), {'b': 2, 'z': 9})


@pytest.mark.parametrize('expected', [5, 5.5, [(5, 'x')], [('a',)], [5]])
def test_update_wrapper_expected_rejects_bad_input(expected):
    def base(a):
        return a

    with pytest.raises(ValueError):
        update_wrapper(lambda *a, **k: None, base, expected=expected)


def test_update_wrapper_injected_and_hide_wrapped():
    def base(a, b=2):
        return a + b

    def wrapper(*args, **kwargs):
        return args, kwargs

    injected = update_wrapper(wrapper, base, injected='b')
    assert injected(1) == ((1,), {})
    assert injected.__wrapped__ is base

    hidden = update_wrapper(wrapper, base, hide_wrapped=True)
    assert not hasattr(hidden, '__wrapped__')


def test_update_wrapper_rejects_classmethod():
    def base(cls, a):
        return a

    with pytest.raises(TypeError):
        update_wrapper(lambda *a, **k: None, classmethod(base))


def test_function_builder_from_func_requires_callable():
    with pytest.raises(TypeError):
        FunctionBuilder.from_func(5)


def test_function_builder_defaults_args_and_removal():
    fb = FunctionBuilder('sample', args=['a', 'b'], defaults=(2,),
                         kwonlyargs=['c'], kwonlydefaults={'c': 3})
    assert fb.get_defaults_dict() == {'b': 2, 'c': 3}
    assert fb.get_arg_names() == ('a', 'b', 'c')
    assert fb.get_arg_names(only_required=True) == ('a',)

    fb.remove_arg('c')
    assert fb.kwonlyargs == []
    fb.remove_arg('a')
    assert fb.args == ['b']
    assert fb.defaults == (2,)

    with pytest.raises(MissingArgument):
        fb.remove_arg('missing')
    with pytest.raises(ExistingArgument):
        fb.add_arg('b')


def test_function_builder_add_kwonly_arg():
    fb = FunctionBuilder('sample')
    fb.add_arg('a')
    fb.add_arg('k', default=7, kwonly=True)
    assert fb.args == ['a']
    assert fb.kwonlyargs == ['k']
    assert fb.kwonlydefaults == {'k': 7}
    assert fb.get_defaults_dict() == {'k': 7}


def test_wraps_factory_copies_metadata():
    def original(a, b=2):
        """original doc"""
        return a + b

    @wraps(original)
    def logged(*args, **kwargs):
        return original(*args, **kwargs)

    assert logged(1) == 3
    assert logged.__name__ == 'original'
    assert logged.__doc__ == 'original doc'
