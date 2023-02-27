"""Tests for `simple_allocator` module."""
from typing import Dict, Tuple
import pytest

from edarop.model import Problem, System, Workload, App, Region, TimeValue, TimeUnit
from edarop.analysis import SolutionAnalyzer
from edarop.visualization import SolutionPrettyPrinter, ProblemPrettyPrinter
from edarop.simple_allocator import SimpleCostAllocator


class TestSimpleCostAllocator:
    """Test class SimpleCostAllocator."""

    @pytest.mark.parametrize("system_wl_four_two_apps", [0.2, 0.01], indirect=True)
    def test_simple_cost_allocator_solve(
        self, system_wl_four_two_apps: Tuple[System, Dict[Tuple[App, Region], Workload]]
    ):
        """Test the solve method of the SimpleCostAllocator class."""
        system, workloads = system_wl_four_two_apps
        problem = Problem(system=system, workloads=workloads)

        alloc = SimpleCostAllocator(problem=problem)
        sol = alloc.solve()

        ProblemPrettyPrinter(problem).print()
        SolutionPrettyPrinter(sol).print(detail_regions=True)

        sol_analyzer = SolutionAnalyzer(sol)

        assert sol_analyzer.cost() == pytest.approx(
            (
                (2 * 1.65 + 2 * 1.65 + 2 * 1.65 + 0 + 2 * 1.65 + 1.65)
                + (0.214 + 0.214 + 0.214 + 0 + 0.428)
            )
        )

        if system.apps[0].max_resp_time == TimeValue(0.2, TimeUnit("s")):
            assert sol_analyzer.deadline_miss_rate() == pytest.approx(0.0)
            miss_rate_per_app = sol_analyzer.miss_rate_per_app()
            for app in miss_rate_per_app:
                assert miss_rate_per_app[app] == pytest.approx(0.0)
        else:
            assert sol_analyzer.deadline_miss_rate() == pytest.approx(0.801271152)
            miss_rate_per_app = sol_analyzer.miss_rate_per_app()
            assert miss_rate_per_app[sol.problem.system.apps[0]] == pytest.approx(1)
            assert miss_rate_per_app[sol.problem.system.apps[1]] == pytest.approx(0)

    @pytest.mark.parametrize("system_wl_four_two_apps", [0.2], indirect=True)
    def test_compute_alloc_time_slot(self, system_wl_four_two_apps: float):
        """Test the compute_alloc_time_slot method for the first time slot."""
        system, workloads = system_wl_four_two_apps
        problem = Problem(system=system, workloads=workloads)

        allocator = SimpleCostAllocator(problem=problem)
        ts_allocation = allocator.compute_alloc_time_slot(0)

        assert len(ts_allocation.ics) == 3
        for ic in ts_allocation.ics:
            assert ts_allocation.ics[ic] == 1

        assert len(ts_allocation.reqs) == 4
