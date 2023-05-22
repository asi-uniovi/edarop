#!/usr/bin/env python

"""Tests for `edarop` package."""
import pytest

from cloudmodel.unified.units import CurrencyPerTime, RequestsPerTime, Time

from edarop.model import (
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
        t_sec = Time("60 s")
        t_min = t_sec.to("min")
        assert t_min.magnitude == 1

    def test_time_value_m_to_s(self):
        """Test TimeValue.to from m to s."""
        t_min = Time("1 min")
        t_sec = t_min.to("s")
        assert t_sec.magnitude == 60

    def test_rpm_to_rps(self):
        """Test RequestsPerTime.to from requests/m to requests/s."""
        rpm = RequestsPerTime("60 req/min")
        rps = rpm.to("req/s")
        assert rps.magnitude == 1

    def test_value_rps_to_rpm(self):
        """Test RequestsPerTime.to from requests/s to requests/m."""
        rps = RequestsPerTime("1 req/s")
        rpm = rps.to("req/min")
        assert rpm.magnitude == 60

    def test_get_regions(self):
        """Test that Problem.regions combines the regions found in the instance
        classes with the ones found in the workload."""
        a0 = App("a0", max_resp_time=Time("0.2 s"))
        regions = [Region("ireland"), Region("paris"), Region("frankfurt")]
        workloads = {
            (a0, regions[0]): Workload(values=[], time_unit="h"),
            (a0, regions[1]): Workload(values=[], time_unit="h"),
        }
        ic = InstanceClass(
            name="test",
            price=CurrencyPerTime("1 usd/h"),
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
        app_a0 = App(name="a0", max_resp_time=Time("0.2 s"))
        system = System(apps=[app_a0], ics=[], perfs={}, latencies={})
        workloads = {
            (app_a0, reg0): Workload(
                values=(10.0, 20.0),
                time_unit=Time("h"),
            ),
            (app_a0, reg1): Workload(
                values=(10.0, 20.0),
                time_unit=Time("s"),
            ),
        }
        with pytest.raises(ValueError):
            Problem(system=system, workloads=workloads)

    def test_same_workload_len(self):
        reg0 = Region("R0")
        reg1 = Region("R1")
        app_a0 = App(name="a0", max_resp_time=Time("0.2 s"))
        system = System(apps=[app_a0], ics=[], perfs={}, latencies={})
        workloads = {
            (app_a0, reg0): Workload(
                values=(10.0, 20.0, 3),
                time_unit=Time("h"),
            ),
            (app_a0, reg1): Workload(
                values=(10.0, 20.0),
                time_unit=Time("s"),
            ),
        }
        with pytest.raises(ValueError):
            Problem(system=system, workloads=workloads)


class TestUniqueNames:
    """These are tests about the names: apps, instance classes and regions
    should have a unique name or an exception should be raised."""

    def test_unique_name_apps(self):
        """Test that an exception is raised when there are repeated app names."""
        a0 = App("an_app", max_resp_time=Time("0.1 s"))
        a1 = App("an_app", max_resp_time=Time("0.2 s"))
        with pytest.raises(ValueError):
            System(apps=[a0, a1], ics=[], perfs={}, latencies={})

    def test_unique_name_ics(self):
        """Test that an exception is raised when there are repeated ic names."""
        reg0 = Region("R0")
        ics = [
            InstanceClass(name="ic0", price=CurrencyPerTime("0.1 usd/s"), region=reg0),
            InstanceClass(name="ic0", price=CurrencyPerTime("0.5 usd/s"), region=reg0),
        ]
        with pytest.raises(ValueError):
            System(apps=[], ics=ics, perfs={}, latencies={})

    def test_unique_name_regions(self):
        """Test that an exception is raised when there are repeated region
        names."""
        reg0 = Region("a_region")
        reg1 = Region("a_region")
        ics = [
            InstanceClass(name="ic0", price=CurrencyPerTime("0.1 usd/s"), region=reg0),
            InstanceClass(name="ic1", price=CurrencyPerTime("0.5 usd/s"), region=reg1),
        ]
        with pytest.raises(ValueError):
            System(apps=[], ics=ics, perfs={}, latencies={})
