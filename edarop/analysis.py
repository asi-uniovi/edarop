"""This module provides ways of analyzingsolutions for edarop."""

from .model import (
    TimeUnit,
    TimeValue,
    Solution,
)


class SolutionAnalyzer:
    """This class carries out computations about cost and response time for
    Solution objects."""

    def __init__(self, sol: Solution):
        self.sol = sol

    def cost(self) -> float:
        """Returns the cost of the allocation inside of the Solution."""
        cost = 0.0
        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]
            for index, num_vms in alloc.ics.items():
                ic = index[1]
                unit_price = ic.price.to(self.sol.problem.time_slot_unit)
                cost += num_vms * unit_price

        return cost

    def avg_resp_time(self) -> TimeValue:
        """Returns the average response time of all requests in seconds."""
        total_resp_time = 0.0
        total_reqs = 0
        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]
            for index, num_reqs in alloc.reqs.items():
                a, e, ic = index
                req_tresp = self.sol.problem.system.tresp(app=a, region=e, ic=ic)
                total_resp_time += num_reqs * req_tresp.to(TimeUnit("s"))

                total_reqs += num_reqs

        if total_reqs == 0:
            return TimeValue(0, TimeUnit("s"))

        return TimeValue(total_resp_time / total_reqs, TimeUnit(("s")))
