from datetime import timedelta, date, datetime, timezone, tzinfo

import pytest

from boltons.timeutils import (daterange, isoparse, Eastern, dt_to_timestamp,
                               parse_timedelta)


def test_daterange_years():
    new_year = date(2017, 1, 1)
    bit_rollover = date(2038, 1, 19)

    new_years_remaining = daterange(new_year, bit_rollover, step=(1, 0, 0))
    assert len(list(new_years_remaining)) == 22

    y2025 = date(2025, 1, 1)
    bakers_years_til_2025 = list(daterange(new_year, y2025, step=(1, 1, 0)))
    assert len(bakers_years_til_2025) == 8
    assert bakers_years_til_2025[-1] == date(2024, 8, 1)
    assert bakers_years_til_2025[-1] == date(2024, 8, 1)

    years_from_2025 = list(daterange(y2025, new_year, step=(-1, 0, 0),
                                     inclusive=True))

    assert years_from_2025[0] == date(2025, 1, 1)
    assert years_from_2025[-1] == date(2017, 1, 1)


def test_daterange_years_step():
    start_day = date(year=2012, month=12, day=25)
    end_day = date(year=2016, month=1, day=1)
    dates = list(daterange(start_day, end_day, step=(1, 0, 0), inclusive=False))
    expected = [date(year=2012, month=12, day=25), date(year=2013, month=12, day=25), date(year=2014, month=12, day=25), date(year=2015, month=12, day=25)]

    assert dates == expected

    dates = list(daterange(start_day, end_day, step=(0, 13, 0), inclusive=False))
    expected = [date(year=2012, month=12, day=25), date(year=2014, month=1, day=25), date(year=2015, month=2, day=25)]
    assert dates == expected
    
    
def test_daterange_infinite():
    today = date.today()
    infinite_dates = daterange(today, None)
    for i in range(10):
        assert next(infinite_dates) == today + timedelta(days=i)


def test_daterange_with_same_start_stop():
    today = date.today()

    date_range = daterange(today, today)
    with pytest.raises(StopIteration):
        next(date_range)

    date_range_inclusive = daterange(today, today, inclusive=True)
    assert next(date_range_inclusive) == today
    with pytest.raises(StopIteration):
        next(date_range_inclusive)



def test_isoparse_basic():
    dt = datetime(2020, 1, 2, 3, 4, 5)
    assert isoparse(dt.isoformat()) == dt


def test_isoparse_fractional_seconds():
    # isoformat() round-trip at every timespec, not just microseconds
    dt = datetime(2020, 1, 2, 3, 4, 5, 851000)
    assert isoparse(dt.isoformat(timespec='milliseconds')) == dt
    assert isoparse(dt.isoformat(timespec='microseconds')) == dt
    assert isoparse(dt.isoformat()) == dt

    # leading zeros in the fraction scale correctly
    assert isoparse('2020-01-02T03:04:05.051').microsecond == 51000
    assert isoparse('2020-01-02T03:04:05.000001').microsecond == 1


def test_isoparse_fraction_overprecise():
    # digits past microsecond precision (e.g. nanosecond timestamps)
    # truncate rather than raise
    assert isoparse('2020-01-01T00:00:00.123456789').microsecond == 123456


def test_isoparse_timezone_suffix():
    assert isoparse('2020-01-02T03:04:05Z') == datetime(
        2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert isoparse('2020-01-02T03:04:05+05:30').utcoffset() == timedelta(
        hours=5, minutes=30)
    assert isoparse('2020-01-02T03:04:05.250-0800').utcoffset() == timedelta(
        hours=-8)
    dt = datetime(2020, 1, 2, 3, 4, 5, 6,
                  tzinfo=timezone(timedelta(hours=-3, minutes=-30)))
    assert isoparse(dt.isoformat()) == dt
    with pytest.raises(ValueError):
        isoparse('2020-01-02T03:04:05+25:00')


def test_dt_to_timestamp_naive_tzinfo():
    # a tzinfo whose utcoffset() is None makes the datetime naive (PEP 495)
    class NaiveTZ(tzinfo):
        def utcoffset(self, dt):
            return None

    assert dt_to_timestamp(datetime(1970, 1, 1, tzinfo=NaiveTZ())) == 0


def test_parse_timedelta_rejects_garbage():
    with pytest.raises(ValueError):
        parse_timedelta('not a duration')
    assert parse_timedelta('') == timedelta(0)
    assert parse_timedelta('  ') == timedelta(0)


def test_daterange_month_step_clamps_day():
    # issue #500: stepping by months from the 31st clamps to month end
    res = list(daterange(date(2020, 1, 31), date(2020, 4, 1), step=(0, 1, 0)))
    assert res == [date(2020, 1, 31), date(2020, 2, 29), date(2020, 3, 29)]



def test_daterange_step_does_not_advance():
    start, stop = date(2020, 1, 1), date(2020, 3, 1)

    with pytest.raises(ValueError):
        list(daterange(start, stop, step=0))

    with pytest.raises(ValueError):
        list(daterange(start, stop, step=(0, 0, 0)))

    # month/day cancellation: +1 month, -31 days is stationary from Jan 1
    with pytest.raises(ValueError):
        list(daterange(start, stop, step=(0, 1, -31)))

    # non-advancing steps raise even for infinite ranges
    with pytest.raises(ValueError):
        list(daterange(start, None, step=0))


def test_daterange_wrong_direction():
    # a step pointed away from stop yields nothing, like range(1, 5, -1)
    assert list(daterange(date(2020, 1, 1), date(2020, 1, 5), step=-1)) == []
    assert list(daterange(date(2020, 1, 5), date(2020, 1, 1), step=1)) == []
    assert list(daterange(date(2020, 1, 1), date(2020, 3, 1),
                          step=(0, -1, 0))) == []


def test_daterange_datetime_hourly():
    # daterange accepts datetimes (datetime subclasses date) with
    # sub-day timedelta steps
    start = datetime(2020, 1, 1, 0)
    stop = datetime(2020, 1, 1, 12)
    hours = list(daterange(start, stop, step=timedelta(hours=3)))
    assert hours == [datetime(2020, 1, 1, 0), datetime(2020, 1, 1, 3),
                     datetime(2020, 1, 1, 6), datetime(2020, 1, 1, 9)]


def test_relative_time_defaults_to_matching_timezone():
    from datetime import datetime, timedelta, timezone
    from boltons.timeutils import decimal_relative_time, relative_time

    for tz in (None, timezone.utc, timezone(timedelta(hours=5, minutes=30))):
        now = (
            datetime.now(tz)
            if tz is not None
            else datetime.now(timezone.utc).replace(tzinfo=None)
        )
        assert decimal_relative_time(now) == (0.0, 'seconds')
        assert relative_time(now) == '0 seconds ago'


def test_us_timezone_dst_fold():
    unfolded = datetime(2011, 11, 6, 1, 30, tzinfo=Eastern, fold=0)
    folded = datetime(2011, 11, 6, 1, 30, tzinfo=Eastern, fold=1)

    assert unfolded.utcoffset() == -4 * timedelta(hours=1)
    assert unfolded.tzname() == 'EDT'
    assert folded.utcoffset() == -5 * timedelta(hours=1)
    assert folded.tzname() == 'EST'


def test_us_timezone_fromutc_sets_fold():
    first = datetime(2011, 11, 6, 5, 30, tzinfo=timezone.utc).astimezone(Eastern)
    second = datetime(2011, 11, 6, 6, 30, tzinfo=timezone.utc).astimezone(Eastern)

    assert first.replace(tzinfo=None) == datetime(2011, 11, 6, 1, 30)
    assert first.fold == 0
    assert first.tzname() == 'EDT'
    assert second.replace(tzinfo=None) == datetime(2011, 11, 6, 1, 30)
    assert second.fold == 1
    assert second.tzname() == 'EST'


def test_dt_to_timestamp_aware():
    assert dt_to_timestamp(datetime(1970, 1, 1, tzinfo=timezone.utc)) == 0.0
    assert dt_to_timestamp(
        datetime(1970, 1, 1, 0, 0, 10, tzinfo=timezone.utc)) == 10.0


def test_parse_timedelta_valid_and_bad_unit():
    assert parse_timedelta('2 weeks 1 day') == timedelta(days=15)
    assert parse_timedelta('-1.5 weeks 3m 20s') == timedelta(
        days=-11, seconds=43400)
    with pytest.raises(ValueError):
        parse_timedelta('5 fortnights')


def test_decimal_relative_time_cardinalization():
    from boltons.timeutils import decimal_relative_time

    now = datetime(2020, 1, 8, 12, 0, 0)
    assert decimal_relative_time(now - timedelta(days=1), now) == (1.0, 'day')
    assert decimal_relative_time(now - timedelta(days=2), now) == (2.0, 'days')
    assert decimal_relative_time(
        now - timedelta(seconds=5), now, cardinalize=False) == (5.0, 'second')


def test_relative_time_future():
    from boltons.timeutils import relative_time

    now = datetime(2020, 1, 8, 12, 0, 0)
    assert relative_time(now + timedelta(days=7), now) == '1 week from now'


def test_strpdate():
    from boltons.timeutils import strpdate

    assert strpdate('2016-02-14', '%Y-%m-%d') == date(2016, 2, 14)
    assert strpdate('20151231 23:59:59',
                    '%Y%m%d %H:%M:%S') == date(2015, 12, 31)


def test_daterange_argument_validation():
    start = date(2020, 1, 1)
    with pytest.raises(TypeError):
        list(daterange('2020-01-01', date(2020, 1, 2)))
    with pytest.raises(TypeError):
        list(daterange(start, '2020-01-02'))
    with pytest.raises(ValueError):
        list(daterange(start, date(2020, 2, 1), step=(0, 0, 'x')))


def test_constant_tzinfo():
    from boltons.timeutils import ConstantTZInfo

    tz = ConstantTZInfo('Custom', timedelta(hours=2))
    assert tz.utcoffset(None) == timedelta(hours=2)
    assert tz.utcoffset_hours == 2.0
    assert tz.tzname(None) == 'Custom'
    assert tz.dst(None) == timedelta(0)
    assert repr(tz) == (
        "ConstantTZInfo(name='Custom', offset=datetime.timedelta(seconds=7200))")


def test_local_tz_methods():
    import time as time_mod
    from boltons.timeutils import LocalTZ

    moment = datetime(2020, 6, 1, 12)
    assert isinstance(LocalTZ.is_dst(moment), bool)
    assert LocalTZ.utcoffset(moment) in (LocalTZ._std_offset, LocalTZ._dst_offset)
    assert LocalTZ.dst(moment) in (
        timedelta(0), LocalTZ._dst_offset - LocalTZ._std_offset)
    assert LocalTZ.tzname(moment) in time_mod.tzname
    assert repr(LocalTZ) == 'LocalTZInfo()'


def test_us_timezone_dst_rules_by_era():
    from boltons.timeutils import USTimeZone

    zone = USTimeZone(-5, 'TestZone', 'TST', 'TDT')
    assert repr(zone) == 'TestZone'

    assert zone._dst_range(1960) == (None, None)
    old = zone._dst_range(1970)
    assert (old[0].year, old[0].month, old[1].month) == (1970, 4, 10)
    mid = zone._dst_range(2000)
    assert (mid[0].year, mid[0].month, mid[1].month) == (2000, 4, 10)
    new = zone._dst_range(2011)
    assert (new[0].month, new[1].month) == (3, 11)

    assert zone.dst(None) == timedelta(0)
    assert zone.dst(datetime(2011, 7, 1)) == timedelta(0)
    assert zone.dst(datetime(1960, 6, 1, tzinfo=zone)) == timedelta(0)
    assert zone.dst(datetime(2011, 7, 1, tzinfo=zone)) == timedelta(hours=1)
    assert zone.dst(datetime(2011, 1, 1, tzinfo=zone)) == timedelta(0)
    assert zone.dst(datetime(2011, 3, 13, 2, 30, tzinfo=zone)) == timedelta(0)
    assert zone.dst(
        datetime(2011, 3, 13, 2, 30, tzinfo=zone, fold=1)) == timedelta(hours=1)


def test_us_timezone_fromutc_edges():
    from boltons.timeutils import USTimeZone

    zone = USTimeZone(-5, 'TestZone', 'TST', 'TDT')
    with pytest.raises(ValueError):
        zone.fromutc(datetime(2011, 7, 1, tzinfo=timezone.utc))

    ancient = zone.fromutc(datetime(1960, 6, 1, tzinfo=zone))
    assert ancient.tzinfo is zone
    assert ancient.replace(tzinfo=None) == datetime(1960, 6, 1) + zone.stdoffset

    winter = zone.fromutc(datetime(2011, 1, 15, tzinfo=zone))
    assert winter.replace(tzinfo=None) == datetime(2011, 1, 15) + zone.stdoffset

    summer = zone.fromutc(datetime(2011, 7, 1, tzinfo=zone))
    assert summer.replace(tzinfo=None) == datetime(2011, 7, 1) + timedelta(hours=-4)
