"""This module provides ways of analyzingsolutions for edarop."""

from .model import TimeUnit, TimeValue, Solution, Status


class SolutionAnalyzer:
    """This class carries out computations about cost and response time for
    Solution objects."""

    def __init__(self, sol: Solution):
        self.sol = sol

    def cost(self) -> float:
        """Returns the cost of the allocation inside of the Solution. If the
        solution is not optimal, it raises an exception."""
        if self.sol.solving_stats.status not in [
            Status.OPTIMAL,
            Status.INTEGER_FEASIBLE,
        ]:
            raise ValueError("Trying to get the cost of a non feasible solution")

        cost = 0.0
        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]
            for index, num_vms in alloc.ics.items():
                ic = index[1]
                unit_price = ic.price.to(self.sol.problem.time_slot_unit)
                cost += num_vms * unit_price

        return cost

    def avg_resp_time(self) -> TimeValue:
        """Returns the average response time of all requests in seconds. If the
        solution is not optimal, it raises an exception."""
        if self.sol.solving_stats.status not in [
            Status.OPTIMAL,
            Status.INTEGER_FEASIBLE,
        ]:
            raise ValueError(
                "Trying to get the avg. resp. time of a non optimal solution"
            )

        total_resp_time = 0.0
        total_reqs = 0
        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]
            for index, num_reqs in alloc.reqs.items():
                a, e, ic = index
                req_resp_time = self.sol.problem.system.resp_time(
                    app=a, region=e, ic=ic
                )
                total_resp_time += num_reqs * req_resp_time.to(TimeUnit("s"))

                total_reqs += num_reqs

        if total_reqs == 0:
            return TimeValue(0, TimeUnit("s"))

        return TimeValue(total_resp_time / total_reqs, TimeUnit(("s")))
