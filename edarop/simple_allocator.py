"""This module contains a class that represents a simple cost-based allocator.
"""
import time
import math
from typing import Dict, Tuple, List

from edarop.model import (
    InstanceClass,
    Status,
    Region,
    App,
    Problem,
    Solution,
    Allocation,
    TimeSlotAllocation,
    SolvingStats,
)


class SimpleCostAllocator:
    """This allocator allocates the cheapest instance class for each app in
    terms of performance per dollar. For each application in each region, it
    selects the cheapest instance class. If two instance classes have the same
    price, it selects the one with the smallest latency. If two instance classes
    have the same performance per dollar and latency, it selects the smallest
    one because it has more flexibility.

    After selecting which instance classes to use, it selects how many VMs of
    each to allocate by adding all the requests of a region for that application
    and dividing by the number of requests per VM.

    It needs a Problem as input. The solve method returns a Solution.
    """

    def __init__(self, problem: Problem):
        self.problem = problem

    def solve(self) -> Solution:
        """Allocates the cheapest instance class for each app in terms of
        performance per dolar. If there are multiple cheapest instance classes,
        it allocates the one with the lowest latency. It returns a Solution."""
        start_solving = time.perf_counter()
        time_slot_allocs = []
        for ts in range(self.problem.workload_len):
            time_slot_allocs.append(self.compute_alloc_time_slot(ts))

        end_solving = time.perf_counter()
        solving_time = end_solving - start_solving

        # Note that many of the stats have no meaning for this allocator
        stats = SolvingStats(
            frac_gap=0.0,  # Menaingless
            max_seconds=0.0,  # Menaingless
            lower_bound=0.0,  # Menaingless
            creation_time=0.0,  # Menaingless
            solving_time=solving_time,
            status=Status.OPTIMAL,
        )

        alloc = Allocation(time_slot_allocs)

        return Solution(problem=self.problem, alloc=alloc, solving_stats=stats)

    def compute_alloc_time_slot(self, time_slot: int) -> TimeSlotAllocation:
        """Gets the allocation for a time slot."""
        wl_ic_app, reqs = self.compute_wl_ic_app(time_slot)

        perfs = self.problem.system.perfs

        # number of ICs per instance class and app
        ics: Dict[Tuple[App, InstanceClass], int] = {}
        ts_unit = self.problem.time_slot_unit
        for (app, ic), wl in wl_ic_app.items():
            perf_ts = perfs[app, ic].value.to(f"reqs / ({ts_unit})").magnitude

            if wl > 0:
                ics[app, ic] = math.ceil(wl / perf_ts)

        return TimeSlotAllocation(ics=ics, reqs=reqs)

    def compute_wl_ic_app(
        self, time_slot: int
    ) -> Tuple[
        Dict[Tuple[App, InstanceClass], int],
        Dict[Tuple[App, Region, InstanceClass], int],
    ]:
        """Computes the workload per instance class and app. It computes the
        instance class that will be used by each app in each region and the
        workload they will have, adding the workload from all regions for the
        same app. It returns a tuple with two dictionaries. The first one
        contains the workload per instance class and app from any region. The
        second one contains the workload per instance class, app, and region."""
        wl_ic_app: Dict[
            Tuple[App, InstanceClass], int
        ] = {}  # number of requests per IC and app from any region

        reqs: Dict[Tuple[App, Region, InstanceClass], int] = {}  # number of requests

        # First, compute the instance classes that will be used by each app
        # in each region and the workload they will have.
        for app in self.problem.system.apps:
            for reg in self.problem.regions:
                # Warning: this assumes everything is per hour, i.e., the time
                # slot size of the workload is 1 hour.
                if (app, reg) not in self.problem.workloads:
                    continue

                workload = self.problem.workloads[app, reg].values[time_slot]

                ic_chooser = InstanceChooser(self.problem)
                ic = ic_chooser.smallest_fastest_cheapest_ic(app, reg)

                if (app, ic) not in wl_ic_app:
                    wl_ic_app[app, ic] = 0

                wl_ic_app[app, ic] += workload.magnitude

                if (app, reg, ic) not in reqs:
                    reqs[app, reg, ic] = 0

                reqs[app, reg, ic] += workload.magnitude

        return wl_ic_app, reqs


class InstanceChooser:
    """Methods to choose between instance classes with different criteria."""

    def __init__(self, problem: Problem):
        self.problem = problem

    def smallest_fastest_cheapest_ic(self, app: App, src_reg: Region) -> InstanceClass:
        """Returns the cheapest instance class for an app. If there are
        multiple instances with the same perf/dolar, it returns the one with the
        lowest response time from src_reg. If there are multiple instances with
        the same perf/dolar and response time, it returns the smallest one in
        terms of cost per period."""
        cheapest_ics = self.cheapest_ics(app)
        fastest_cheapest_ics = self.fastest_ics(src_reg, cheapest_ics, app)
        return self.smallest_ic(fastest_cheapest_ics)

    def smallest_ic(self, ics: List[InstanceClass]) -> InstanceClass:
        """Returns the smallest instance class in terms of cost per period. It
        assumes that all the ics have the same performance per monetary unit."""
        return min(ics, key=lambda ic: ic.price)

    def response_time(self, src_reg: Region, ic: InstanceClass, app: App) -> float:
        """Returns the response time in seconds of an app from a source region
        using an instance class."""
        net_latency = self.problem.system.latencies[src_reg, ic.region].value
        server_response_time = self.problem.system.perfs[app, ic].slo
        return (net_latency + server_response_time).to("s").magnitude

    def fastest_ics(
        self, src_reg: Region, ics: List[InstanceClass], app: App
    ) -> List[InstanceClass]:
        """Returns a list of the ics with the lowest sum of network latency and
        server response time for an app from src_reg."""
        latencies = self.problem.system.latencies
        ic_resp_times = {}
        for ic in ics:
            if (src_reg, ic.region) in latencies:
                ic_resp_times[ic] = self.response_time(src_reg, ic, app)

        min_resp_time = min(ic_resp_times.values())
        return [
            ic for ic, resp_time in ic_resp_times.items() if resp_time == min_resp_time
        ]

    def cheapest_ics(self, app: App) -> List[InstanceClass]:
        """Returns the cheapest instance classes per request for an app."""
        ics = self.problem.system.ics
        perfs = self.problem.system.perfs
        ic_dollar_per_req = {ic: ic.price / perfs[app, ic].value for ic in ics}

        min_dolar_per_req = min(ic_dollar_per_req.values())
        return [
            ic for ic in ic_dollar_per_req if ic_dollar_per_req[ic] == min_dolar_per_req
        ]
