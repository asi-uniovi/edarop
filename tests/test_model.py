#!/usr/bin/env python

"""Tests for `edarop` package."""
from edarop import cli
from edarop.model import (
    TimeUnit,
    TimeValue,
    TimeRatioValue,
    InstanceClass,
    Region,
    App,
    System,
    Problem,
)


class TestModel:
    """Tests the model classes."""

    def test_time_value_s_to_m(self):
        """Test TimeValue.to from s to m."""
        t_sec = TimeValue(60, TimeUnit("s"))
        t_min = t_sec.to(TimeUnit("m"))
        assert t_min == 1

    def test_time_value_m_to_s(self):
        """Test TimeValue.to from m to s."""
        t_min = TimeValue(1, TimeUnit("m"))
        t_sec = t_min.to(TimeUnit("s"))
        assert t_sec == 60

    def test_time_ratio_value_rpm_to_rps(self):
        """TEst TimeRatioValue.to from requests/m to requests/s."""
        rpm = TimeRatioValue(60, TimeUnit("m"))
        rps = rpm.to(TimeUnit("s"))
        assert rps == 1

    def test_time_ratio_value_rps_to_rpm(self):
        """TEst TimeRatioValue.to from requests/s to requests/m."""
        rps = TimeRatioValue(1, TimeUnit("s"))
        rpm = rps.to(TimeUnit("m"))
        assert rpm == 60

    def test_get_regions(self):
        """Test that Problem.regions combines the regions found in the instance
        classes with the ones found in the workload"""
        a0 = App("a0")
        regions = [Region("ireland"), Region("paris"), Region("frankfurt")]
        workloads = {
            (a0, regions[0]): [],
            (a0, regions[1]): [],
        }
        ic = InstanceClass(
            name="test",
            price=TimeRatioValue(1, TimeUnit("h")),
            region=regions[2],
        )
        system = System(apps=None, ics=[ic], perfs=None, latencies=None)
        p = Problem(system=system, workloads=workloads)
        assert set(p.regions) == set(regions)
