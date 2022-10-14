#!/usr/bin/env python

"""Tests for `edarop` package."""
import pytest

from edarop import cli
from edarop.model import (
    TimeUnit,
    TimeValue,
    TimeRatioValue,
    InstanceClass,
    Workload,
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
        classes with the ones found in the workload."""
        a0 = App("a0")
        regions = [Region("ireland"), Region("paris"), Region("frankfurt")]
        workloads = {
            (a0, regions[0]): Workload(values=[], time_unit="h"),
            (a0, regions[1]): Workload(values=[], time_unit="h"),
        }
        ic = InstanceClass(
            name="test",
            price=TimeRatioValue(1, TimeUnit("h")),
            region=regions[2],
        )
        system = System(apps=[a0], ics=[ic], perfs=None, latencies=None)
        p = Problem(system=system, workloads=workloads)
        assert set(p.regions) == set(regions)


class TestWorkload:
    """These are tests about the workload: it should have the same time unit for
    all workloads and the length of all workloads should be the same. If any of
    these conditions is broken, an exception should be raised."""

    def test_same_workload_units(self):
        reg0 = Region("R0")
        reg1 = Region("R1")
        app_a0 = App(name="a0", max_resp_time=TimeValue(0.2, TimeUnit("s")))
        system = System(apps=[app_a0], ics=[], perfs={}, latencies={})
        workloads = {
            (app_a0, reg0): Workload(
                values=(10.0, 20.0),
                time_unit=TimeUnit("h"),
            ),
            (app_a0, reg1): Workload(
                values=(10.0, 20.0),
                time_unit=TimeUnit("s"),
            ),
        }
        with pytest.raises(ValueError):
            Problem(system=system, workloads=workloads)

    def test_same_workload_len(self):
        reg0 = Region("R0")
        reg1 = Region("R1")
        app_a0 = App(name="a0", max_resp_time=TimeValue(0.2, TimeUnit("s")))
        system = System(apps=[app_a0], ics=[], perfs={}, latencies={})
        workloads = {
            (app_a0, reg0): Workload(
                values=(10.0, 20.0, 3),
                time_unit=TimeUnit("h"),
            ),
            (app_a0, reg1): Workload(
                values=(10.0, 20.0),
                time_unit=TimeUnit("s"),
            ),
        }
        with pytest.raises(ValueError):
            Problem(system=system, workloads=workloads)


class TestUniqueNames:
    """These are tests about the names: apps, instance classes and regions
    should have a unique name or an exception should be raised."""

    def test_unique_name_apps(self):
        """Test that an exception is raised when there are repeated app names."""
        a0 = App("an_app")
        a1 = App("an_app")
        with pytest.raises(ValueError):
            System(apps=[a0, a1], ics=[], perfs={}, latencies={})

    def test_unique_name_ics(self):
        """Test that an exception is raised when there are repeated ic names."""
        reg0 = Region("R0")
        ics = [
            InstanceClass(name="ic0", price=TimeRatioValue(0.1, "s"), region=reg0),
            InstanceClass(name="ic0", price=TimeRatioValue(0.5, "s"), region=reg0),
        ]
        with pytest.raises(ValueError):
            System(apps=[], ics=ics, perfs={}, latencies={})

    def test_unique_name_regions(self):
        """Test that an exception is raised when there are repeated region
        names."""
        reg0 = Region("a_region")
        reg1 = Region("a_region")
        ics = [
            InstanceClass(name="ic0", price=TimeRatioValue(0.1, "s"), region=reg0),
            InstanceClass(name="ic1", price=TimeRatioValue(0.5, "s"), region=reg1),
        ]
        with pytest.raises(ValueError):
            System(apps=[], ics=ics, perfs={}, latencies={})
