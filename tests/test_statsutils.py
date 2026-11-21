import pytest

from boltons.statsutils import Stats, mode, describe, format_histogram_counts


def test_stats_basic():
    da = Stats(range(20))
    assert da.mean == 9.5
    assert round(da.std_dev, 2) == 5.77
    assert da.variance == 33.25
    assert da.skewness == 0
    assert round(da.kurtosis, 1) == 1.9
    assert da.median == 9.5


def test_pearson_type_covers_kappa_ge_zero():
    assert Stats([8, 4, 4, 4, 5, 1, 6, 5]).pearson_type == 4
    assert Stats([5, 5, 2, 4, 5, 9, 5, 5]).pearson_type == 5
    assert Stats([0, 0, 0, 0, 0, 0, -11, 17]).pearson_type == 6


def test_mode():
    assert Stats([2, 1, 3, 1]).mode == 1
    # ties resolve to the value seen first in the data
    assert mode([1, 1, 2, 2, 3]) == 1
    # non-numeric, categorical data is supported
    assert mode(['a', 'b', 'b', 'c', 'c', 'c']) == 'c'
    # empty data falls back to the configured default
    assert Stats([], default=None).mode is None


def test_pearson_type_zero_denominator():
    # Supply exact moments to exercise c0 == 0, c2 == 0, and the
    # normal-distribution boundary without sampling noise.
    for skewness, kurtosis, expected in ((2.0, 3.0, 1),
                                         (2.0, 9.0, 3),
                                         (0.0, 3.0, 0)):
        stats = Stats([0])
        stats.skewness = skewness
        stats.kurtosis = kurtosis
        assert stats.pearson_type == expected


def test_histogram_zero_interquartile_range():
    for data in ([5] * 10, [0] * 10 + [100]):
        counts = Stats(data).get_histogram_counts()
        assert counts == [(float(min(data)), len(data))]


def test_sorted_measures_keep_data_order():
    # see #534
    stats = Stats([2, 1, 2, 1])
    assert stats.median == 1.5
    assert stats.mode == 2
    assert stats.data == [2, 1, 2, 1]


def test_clear_cache_resets_is_sorted():
    # see #570
    stats = Stats([1, 2, 3], is_sorted=True)
    assert stats.min == 1
    stats.data.append(0)
    stats.clear_cache()
    assert stats.min == 0
    assert stats.median == 1.5


def test_format_histogram_counts_all_zero():
    # see #529
    from boltons.statsutils import format_histogram_counts

    assert format_histogram_counts([(0.0, 0), (1.0, 0)]) == '0.0: 0 |\n1.0: 0 |'


def test_len_and_iter_use_original_order():
    stats = Stats([3, 1, 2])
    assert len(stats) == 3
    assert list(stats) == [3, 1, 2]
    assert stats.count == 3


def test_use_copy_false_sorts_lazily():
    data = [3, 1, 2]
    stats = Stats(data, use_copy=False)
    assert stats.median == 2
    # no copy is made, the caller keeps ownership of the data
    assert stats.data is data


def test_is_sorted_uses_first_and_last_values():
    stats = Stats([1, 2, 3], is_sorted=True)
    assert stats.min == 1
    assert stats.max == 3


def test_iqr_trimean_and_mad():
    stats = Stats(range(5))
    assert stats.iqr == 2
    assert stats.trimean == 2.0
    assert stats.mad == 1.0
    assert stats.median_abs_dev == 1.0


def test_rel_std_dev():
    assert Stats([2, 2, 2]).rel_std_dev == 0.0
    assert Stats([-1, 1], default=None).rel_std_dev is None


def test_skewness_and_kurtosis_degenerate_defaults():
    single = Stats([5], default=-1.0)
    assert single.skewness == -1.0
    assert single.kurtosis == 0.0
    constant = Stats([2, 2, 2])
    assert constant.skewness == 0.0
    assert constant.kurtosis == 0.0


def test_pearson_type_symmetric_beta_and_type_seven():
    stats = Stats([0])
    stats.skewness = 0.0
    stats.kurtosis = 2.0
    assert stats.pearson_type == 2

    stats = Stats([0])
    stats.skewness = 0.0
    stats.kurtosis = 4.0
    assert stats.pearson_type == 7


def test_pearson_type_negative_k_is_beta():
    stats = Stats([0])
    stats.skewness = 1.0
    stats.kurtosis = 2.0
    assert stats.pearson_type == 1


def test_get_quantile_bounds_validation_and_empty_default():
    stats = Stats(range(4), default=-1.0)
    assert stats.get_quantile(0.0) == 0
    assert stats.get_quantile(1.0) == 3
    # idx lands exactly on an element, so no interpolation is needed
    assert stats.get_quantile(1 / 3) == 1

    with pytest.raises(ValueError):
        stats.get_quantile(1.5)

    assert Stats([], default=None).get_quantile(0.5) is None


def test_get_zscore_constant_data():
    stats = Stats([4, 4, 4])
    assert stats.get_zscore(4) == 0
    assert stats.get_zscore(5) == float('inf')
    assert stats.get_zscore(3) == float('-inf')


def test_get_zscore():
    # variance is 2/3, so the standard deviation is 1/sqrt(1.5)
    assert Stats([1, 2, 3]).get_zscore(4) == pytest.approx(2.449489742783178)


def test_trim_relative():
    stats = Stats(range(10))
    stats.trim_relative(0.2)
    assert stats.data == [2, 3, 4, 5, 6, 7]
    assert stats.median == 4.5

    # too small a proportion trims nothing
    unchanged = Stats(range(10))
    unchanged.trim_relative(0.01)
    assert unchanged.data == list(range(10))

    with pytest.raises(ValueError):
        stats.trim_relative(0.5)


def test_get_bin_bounds_small_data_and_with_max():
    stats = Stats([1, 2, 3])
    bounds = stats._get_bin_bounds()
    assert len(bounds) == 3
    assert bounds[0] == 1.0
    with_max = stats._get_bin_bounds(with_max=True)
    assert with_max[-1] == 3.0
    assert len(with_max) == len(bounds) + 1
    assert Stats([])._get_bin_bounds() == [0.0]


def test_get_histogram_counts_explicit_bins_and_validation():
    stats = Stats([0, 5, 10])
    counts = stats.get_histogram_counts([2.0, 6.0])
    # a boundary below the data's minimum is prepended
    assert counts[0][0] == 0.0
    assert sum(count for _, count in counts) == 3

    assert sum(c for _, c in Stats(range(6)).get_histogram_counts(3)) == 6

    with pytest.raises(TypeError):
        stats.get_histogram_counts(bogus=1)
    with pytest.raises(ValueError):
        stats.get_histogram_counts(['a', 'b'])


def test_describe_formats_and_validation():
    stats = Stats(range(1, 8))
    as_dict = stats.describe()
    assert as_dict['count'] == 7
    assert as_dict['mean'] == 4.0
    assert as_dict['0.5'] == 4

    as_list = stats.describe(format='list')
    assert as_list[0] == ('count', 7)
    assert as_list[-1] == ('max', 7)

    text = stats.describe(format='text')
    assert text.startswith('count:    7')
    assert text.endswith('max:      7')

    with pytest.raises(ValueError):
        stats.describe(format='csv')

    single_quantile = stats.describe(quantiles=[0.5])
    assert single_quantile == {'count': 7, 'mean': 4.0, 'std_dev': 2.0,
                               'mad': 2.0, 'min': 1, '0.5': 4, 'max': 7}

    assert describe(range(7))['mean'] == 3.0


def test_format_histogram_counts_custom_width_and_label():
    out = format_histogram_counts([(0, 1), (1, 2)],
                                  width=20,
                                  format_bin=lambda b: '%sm' % b)
    first, second = out.splitlines()
    assert first.startswith('0m: 1 ')
    assert second.startswith('1m: 2 ')


def test_format_histogram_counts_terminal_fallback(monkeypatch):
    import shutil

    def unavailable(*args, **kwargs):
        raise RuntimeError('no terminal available')

    monkeypatch.setattr(shutil, 'get_terminal_size', unavailable)
    out = format_histogram_counts([(0.0, 1), (1.0, 2)])
    assert out.splitlines()[0].startswith('0.0: 1 ')
