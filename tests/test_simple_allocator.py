"""Tests for `simple_allocator` module."""
import pytest

from edarop.model import (
    Problem,
)
from edarop.analysis import SolutionAnalyzer
from edarop.visualization import SolutionPrettyPrinter, ProblemPrettyPrinter
from edarop.simple_allocator import SimpleCostAllocator


class TestSimpleCostAllocator:
    """Test class SimpleCostAllocator."""

    def test_simple_cost_allocator_solve(self, system_wl_four_two_apps):
        """Test the solve method of the SimpleCostAllocator class."""
        system, workloads = system_wl_four_two_apps
        problem = Problem(system=system, workloads=workloads)

        alloc = SimpleCostAllocator(problem=problem)
        sol = alloc.solve()

        ProblemPrettyPrinter(problem).print()
        SolutionPrettyPrinter(sol).print(detail_regions=True)

        assert SolutionAnalyzer(sol).cost() == pytest.approx(
            (
                (2 * 1.65 + 2 * 1.65 + 2 * 1.65 + 0 + 2 * 1.65 + 1.65)
                + (0.214 + 0.214 + 0.214 + 0 + 0.428)
            )
        )

    def test_compute_alloc_time_slot(self, system_wl_four_two_apps):
        """Test the compute_alloc_time_slot method for the first time slot."""
        system, workloads = system_wl_four_two_apps
        problem = Problem(system=system, workloads=workloads)

        allocator = SimpleCostAllocator(problem=problem)
        ts_allocation = allocator.compute_alloc_time_slot(0)

        assert len(ts_allocation.ics) == 3
        for ic in ts_allocation.ics:
            assert ts_allocation.ics[ic] == 1

        assert len(ts_allocation.reqs) == 4
