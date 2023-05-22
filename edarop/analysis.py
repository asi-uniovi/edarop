"""This module provides ways of analyzingsolutions for edarop."""
from typing import Dict

from cloudmodel.unified.units import Currency, Time

from .model import Solution, Status, App


class SolutionAnalyzer:
    """This class carries out computations about cost and response time for
    Solution objects."""

    def __init__(self, sol: Solution):
        self.sol = sol

    def cost(self) -> Currency:
        """Returns the cost of the allocation inside of the Solution. If the
        solution is not optimal, it raises an exception."""
        if self.sol.solving_stats.status not in [
            Status.OPTIMAL,
            Status.INTEGER_FEASIBLE,
        ]:
            raise ValueError("Trying to get the cost of a non feasible solution")

        cost = Currency("0.0 usd")
        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]
            for index, num_vms in alloc.ics.items():
                ic = index[1]
                unit_price = ic.price * self.sol.problem.time_slot_unit
                cost += num_vms * unit_price

        return cost

    def avg_resp_time(self) -> Time:
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
                total_resp_time += num_reqs * req_resp_time.to("s").magnitude

                total_reqs += num_reqs

        if total_reqs == 0:
            return Time("0 s")

        return Time(f"{total_resp_time / total_reqs} s")

    def deadline_miss_rate(self) -> float:
        """Returns the deadline miss rate of the solution. If the solution is
        not optimal or feasible, it raises an exception."""
        if self.sol.solving_stats.status not in [
            Status.OPTIMAL,
            Status.INTEGER_FEASIBLE,
        ]:
            raise ValueError(
                "Trying to get the deadline miss rate of a non optimal solution"
            )

        total_missed_reqs = 0
        total_reqs = 0
        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]
            for index, num_reqs in alloc.reqs.items():
                app, region, ic = index
                req_resp_time = self.sol.problem.system.resp_time(
                    app=app, region=region, ic=ic
                )
                if req_resp_time > app.max_resp_time:
                    total_missed_reqs += num_reqs

                total_reqs += num_reqs

        return total_missed_reqs / total_reqs

    def total_reqs_per_app(self) -> Dict[App, int]:
        """Returns the total number of requests per application."""
        result = {}
        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]
            for index, num_reqs in alloc.reqs.items():
                app, _, _ = index
                if app not in result:
                    result[app] = 0

                result[app] += num_reqs

        return result

    def total_missed_reqs_per_app(self) -> Dict[App, int]:
        """Returns the total number of missed requests per application."""
        result = {}
        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]
            for index, num_reqs in alloc.reqs.items():
                if num_reqs == 0:
                    continue  # No requests allocated, no missed requests

                app, region, ic = index

                if app not in result:
                    result[app] = 0

                req_resp_time = self.sol.problem.system.resp_time(
                    app=app, region=region, ic=ic
                )
                if req_resp_time > app.max_resp_time:
                    result[app] += num_reqs

        return result

    def miss_rate_per_app(self) -> Dict[App, float]:
        """Returns the deadline miss rate per application."""
        result = {}
        miss_reqs_per_app = self.total_missed_reqs_per_app()
        total_reqs_per_app = self.total_reqs_per_app()
        for app in self.sol.problem.system.apps:
            if app in miss_reqs_per_app:
                result[app] = miss_reqs_per_app[app] / total_reqs_per_app[app]
            else:
                result[app] = 0.0

        return result
