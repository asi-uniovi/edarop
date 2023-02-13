"""Tests for `simple_allocator` module."""
from edarop.model import (
    Problem,
)
from edarop.simple_allocator import InstanceChooser


class TestSimpleCostAllocator:
    """Basic tests with only two regions, two instance classes, two apps."""

    def test_cheapest_ics(self, system_wl_four_two_apps):
        """Tests the cheapest_ics method of the InstanceChooser class."""
        system, workloads = system_wl_four_two_apps
        problem = Problem(system=system, workloads=workloads)
        ic_chooser = InstanceChooser(problem=problem)

        cheapest_ics_a0 = ic_chooser.cheapest_ics(system.apps[0])
        assert len(cheapest_ics_a0) == 2
        assert cheapest_ics_a0[0].name == "c3.medium_madrid"
        assert cheapest_ics_a0[1].name == "c3.medium_dublin"

        cheapest_ics_a1 = ic_chooser.cheapest_ics(system.apps[1])
        assert len(cheapest_ics_a1) == 1
        assert cheapest_ics_a1[0].name == "m5.xlarge_ireland"

    def test_fastest_ics(self, system_wl_four_two_apps):
        """Tests the fastest_ics method of the InstanceChooser class."""
        system, workloads = system_wl_four_two_apps
        problem = Problem(system=system, workloads=workloads)
        ic_chooser = InstanceChooser(problem=problem)

        # Tests with the Dublin region and app 0
        dublin_region = problem.regions[-1]
        app0 = system.apps[0]

        closest_dublin_ics = ic_chooser.fastest_ics(dublin_region, system.ics, app0)

        assert len(closest_dublin_ics) == 2
        assert closest_dublin_ics[0].name == "c3.medium_dublin"
        assert closest_dublin_ics[1].name == "m3.large_dublin"

        # Tests with the Madrid region
        madrid_region = problem.regions[-2]

        closest_madrid_ics = ic_chooser.fastest_ics(madrid_region, system.ics, app0)

        assert len(closest_madrid_ics) == 2
        assert closest_madrid_ics[0].name == "c3.medium_madrid"
        assert closest_madrid_ics[1].name == "m3.large_madrid"

    def test_smallest_ic(self, system_wl_four_two_apps):
        """Tests the smallest_ic method of the InstanceChooser class."""
        system, workloads = system_wl_four_two_apps
        problem = Problem(system=system, workloads=workloads)
        ic_chooser = InstanceChooser(problem=problem)

        smallest_ic = ic_chooser.smallest_ic(system.ics)

        assert smallest_ic.name == "m5.xlarge_ireland"
