"""Main module for the edarop package. It defines the base class
EdaropAllocator, which is the base class for two allocators: EdaropCAllocator,
which minimizes cost, and EdaropRAllocator, which minimizes response time. They
receive a edarop problem and construct and solve the corresponding linear
programming problem using pulp."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from typing import Dict, List
from functools import partial

from pulp import LpVariable, lpSum, LpProblem, LpMinimize, value, LpStatus
from pulp.constants import LpInteger, LpBinary

from .model import (
    TimeUnit,
    Problem,
    Solution,
    InstanceClass,
    App,
    Region,
    Allocation,
    TimeSlotAllocation,
    pulp_to_edarop_status,
)


@dataclass
class XVarInfo:
    """Stores information about the app, instance class and time slot for an
    X variable. The price and performance is stored using as time unit one time
    slot."""

    app: App
    ic: InstanceClass
    time_slot: int
    price_per_ts: float  # per time slot
    perf_per_ts: float  # per time slot


@dataclass
class YVarInfo:
    """Stores information about the app, region, instance class and time slot
    for a Y variable."""

    app: App
    region: Region
    ic: InstanceClass
    time_slot: int


class EdaropAllocator(ABC):
    """This abstract base class receives a problem of  optimization for an edge
    architecture and gives methods to solve it and store the solution."""

    def __init__(self, problem: Problem):
        """Constructor.

        Args:
            problem: problem to solve."""
        self.problem = problem
        self.lp_problem = LpProblem("edarop_problem", LpMinimize)

        self.x: LpVariable = LpVariable(name="X")  # Placeholders
        self.x_names: List[str] = []
        self.x_info: Dict[str, XVarInfo] = {}  # The string is the var name

        self.y: LpVariable = LpVariable(name="Y")
        self.y_names: List[str] = []
        self.y_info: Dict[str, YVarInfo] = {}  # The string is the var name

    def solve(self) -> Solution:
        """Solve the linear programming problem and return the solution."""
        self._create_vars()
        self._create_objective()
        self._create_contraints()

        self.lp_problem.solve()

        return self._compose_solution()

    @staticmethod
    def _aik_name(a: App, i: InstanceClass, k: int) -> str:
        """Returns the name for an X variable from the app, instance class and
        time slot."""
        return f"{a.name}_{i.name}_{k}"

    @staticmethod
    def _aeik_name(a: App, e: Region, i: InstanceClass, k: int) -> str:
        """Returns the name for a Y or Z variable from the app, region, instance
        class and time slot."""
        return f"{a.name}_{e.name}_{i.name}_{k}"

    def _create_vars_x(self):
        """Creates the X variables for the linear programming algorithm. Each
        X_aik variable represents the number of VMs for the app a of the
        instance class i at the time slot k."""
        for a in self.problem.system.apps:
            for i in self.problem.system.ics:
                for k in range(self.problem.workload_len):
                    if (a, i) not in self.problem.system.perfs.keys():
                        # This instance class cannot run this app
                        continue

                    x_name = EdaropAllocator._aik_name(a, i, k)
                    self.x_names.append(x_name)

                    ts_unit = self.problem.time_slot_unit

                    perf = self.problem.system.perfs[a, i]
                    perf_per_ts = perf.value.to(ts_unit)

                    price_per_ts = i.price.to(ts_unit)
                    self.x_info[x_name] = XVarInfo(
                        app=a,
                        ic=i,
                        time_slot=k,
                        price_per_ts=price_per_ts,
                        perf_per_ts=perf_per_ts,
                    )

        self.x = LpVariable.dicts(
            name="X", indices=self.x_names, lowBound=0, cat=LpInteger
        )

    def _create_vars_y(self):
        """Creates the Y variables for the linear programming algorithm. Each
        Y_aeik variable represents the number of requests for the app a from the
        edge region e served by the instance class i in the time slot k."""
        for a in self.problem.system.apps:
            for e in self.problem.regions:
                for i in self.problem.system.ics:
                    for k in range(self.problem.workload_len):
                        if self._can_send_requests(e, i.region):
                            y_name = EdaropAllocator._aeik_name(a, e, i, k)
                            self.y_names.append(y_name)
                            self.y_info[y_name] = YVarInfo(
                                app=a, region=e, ic=i, time_slot=k
                            )

        self.y = LpVariable.dicts(
            name="Y", indices=self.y_names, lowBound=0, cat=LpInteger
        )

    def _create_vars(self):
        """Creates the variables for the linear programming algorithm."""
        self._create_vars_x()
        self._create_vars_y()

        logging.info("There are %s X variables", len(self.x))
        logging.info("There are %s Y variables", len(self.y))

    @abstractmethod
    def _create_objective(self):
        """Adds the function to optimize."""

    def _is_x_app_and_timeslot(self, x_name: str, app: App, time_slot: int) -> bool:
        """Returns true if a X variable name corresponds to an app and a
        time slot."""
        return (
            self.x_info[x_name].app == app
            and self.x_info[x_name].time_slot == time_slot
        )

    def _is_y_app_ic_and_timeslot(
        self, y_name: str, app: App, ic: InstanceClass, time_slot: int
    ) -> bool:
        """Returns true if a Y variable name corresponds to an app, an instance
        class and a time slot."""
        return (
            self.y_info[y_name].app == app
            and self.y_info[y_name].ic == ic
            and self.y_info[y_name].time_slot == time_slot
        )

    def _is_y_app_region_and_timeslot(
        self, y_name: str, app: App, region: Region, time_slot: int
    ) -> bool:
        """Returns true if a Y variable name corresponds to an app, a region and
        a time slot."""
        return (
            self.y_info[y_name].app == app
            and self.y_info[y_name].region == region
            and self.y_info[y_name].time_slot == time_slot
        )

    def _is_y_app_and_timeslot(self, y_name: str, app: App, time_slot: int) -> bool:
        """Returns true if a Y variable name corresponds to an app and a time
        slot."""
        return (
            self.y_info[y_name].app == app
            and self.y_info[y_name].time_slot == time_slot
        )

    def _workload_for_app_in_time_slot(self, a: App, k: int) -> float:
        """Returns the workload for app a at time slot k for any region."""
        l_ak = 0.0
        for r in self.problem.regions:
            if (a, r) in self.problem.workloads:
                l_ak += self.problem.workloads[(a, r)].values[k]

        return l_ak

    def _create_contraints_throughput_per_app(self):
        """Adds throughput contraints per app and time slot: the performance
        of all the VMs for an app at a time slot has to be equal to or greater
        than the workload for that app at that time slot."""
        for a in self.problem.system.apps:
            for k in range(self.problem.workload_len):
                filter_app_and_timeslot = partial(
                    self._is_x_app_and_timeslot, app=a, time_slot=k
                )
                x_names = filter(filter_app_and_timeslot, self.x_names)

                l_ak = self._workload_for_app_in_time_slot(a=a, k=k)

                self.lp_problem += (
                    lpSum(
                        self.x[x_name] * self.x_info[x_name].perf_per_ts
                        for x_name in x_names
                    )
                    >= l_ak,
                    f"The performance of all VMs for app {a.name} has to be equal to"
                    f" or greater than {l_ak}, the workload for that app at"
                    f" time slot {k}",
                )

    def _create_contraints_throughput_per_ic(self):
        """Adds throughput contraints per ic and time slot: the performance
        of an instance class has to be equal to or greater than the number of
        requests from any region assigned to it for all apps at any time
        slot."""
        for a in self.problem.system.apps:
            for i in self.problem.system.ics:
                for k in range(self.problem.workload_len):
                    if (a, i) not in self.problem.system.perfs:
                        # This instance class cannot run this app
                        continue

                    filter_app_ic_and_timeslot = partial(
                        self._is_y_app_ic_and_timeslot, app=a, ic=i, time_slot=k
                    )
                    y_names = filter(filter_app_ic_and_timeslot, self.y_names)

                    x_name = EdaropAllocator._aik_name(a, i, k)

                    total_x_perf = self.x[x_name] * self.x_info[x_name].perf_per_ts

                    self.lp_problem += (
                        total_x_perf >= lpSum(self.y[y_name] for y_name in y_names),
                        f"The performance of ic {i.name} for app {a.name}"
                        f" in time slot {k} has to be greater than or equal"
                        f" to the number of requests assigned to it",
                    )

    def _create_constraints_throughput_all_regions(self):
        """Adds throughput contraints of all regions and time slot: the sum of
        the requests processed in all regions has to be equal to the workload
        for all apps at any time slot."""
        for a in self.problem.system.apps:
            for k in range(self.problem.workload_len):
                l_ak = self._workload_for_app_in_time_slot(a=a, k=k)

                filter_app_and_timeslot = partial(
                    self._is_y_app_and_timeslot, app=a, time_slot=k
                )
                y_names = filter(filter_app_and_timeslot, self.y_names)

                self.lp_problem += (
                    lpSum(self.y[y_name] for y_name in y_names) == l_ak,
                    f"The sum of requests for app {a.name} in time slot {k} in"
                    f" any region has to be equal to the workload ({l_ak})",
                )

    def _create_constraints_throughput_per_region(self):
        """Adds throughput contraints for each app, region and time slot: the
        sum of the requests processed comming from a region in any instance
        class has to be equal to the workload from that region at that time slot
        for that app."""
        for a in self.problem.system.apps:
            for e in self.problem.regions:
                if (a, e) not in self.problem.workloads:
                    # Some apps might not have workload in a region
                    continue

                for k in range(self.problem.workload_len):
                    l_aek = self.problem.workloads[(a, e)].values[k]

                    filter_app_region_and_timeslot = partial(
                        self._is_y_app_region_and_timeslot,
                        app=a,
                        region=e,
                        time_slot=k,
                    )
                    y_names = list(filter(filter_app_region_and_timeslot, self.y_names))

                    if not y_names:
                        continue

                    self.lp_problem += (
                        lpSum(self.y[y_name] for y_name in y_names) == l_aek,
                        f"The sum of requests for app {a.name} in time slot {k} from"
                        f" region {e} has to be equal to the workload ({l_aek})",
                    )

    def _create_contraints(self):
        """Adds the contraints."""
        self._create_contraints_throughput_per_app()
        self._create_contraints_throughput_per_ic()
        self._create_constraints_throughput_all_regions()
        self._create_constraints_throughput_per_region()

    def _can_send_requests(self, src: Region, dst: Region) -> bool:
        """Returns true if requests can be sent from src to dst. It assumes that
        if there is latency data, it is possible."""
        return (src, dst) in self.problem.system.latencies

    def _get_alloc(self, time_slot: int) -> TimeSlotAllocation:
        ics = {}
        reqs = {}
        for a in self.problem.system.apps:
            for i in self.problem.system.ics:
                aik_name = EdaropAllocator._aik_name(a, i, time_slot)
                if aik_name not in self.x:
                    # Some instances might not be able to run an app
                    continue

                ics[a, i] = self.x[aik_name].value()

                for r in self.problem.regions:
                    if self._can_send_requests(r, i.region):
                        aeik_name = EdaropAllocator._aeik_name(a, r, i, time_slot)
                        reqs[a, r, i] = self.y[aeik_name].value()

        return TimeSlotAllocation(ics, reqs)

    def _compose_solution(self) -> Solution:
        self._log_solution()

        alloc = Allocation(
            time_slot_allocs=[
                self._get_alloc(k) for k in range(self.problem.workload_len)
            ]
        )
        return Solution(
            problem=self.problem,
            alloc=alloc,
            status=pulp_to_edarop_status(self.lp_problem.status),
        )

    @staticmethod
    def _log_var(variables: LpVariable):
        for var in variables.values():
            if var.value() > 0:
                logging.info("  %s = %i", var, var.value())

        logging.info("")

    def _log_solution(self):
        logging.info("Solution (only variables different to 0):")

        EdaropAllocator._log_var(self.x)
        EdaropAllocator._log_var(self.y)

        logging.info("Status: %s", LpStatus[self.lp_problem.status])
        logging.info("Total cost: %f", value(self.lp_problem.objective))


class EdaropCAllocator(EdaropAllocator):
    """This class receives a cost optimization problem for an edge architecture
    and gives methods to solve it and store the solution."""

    def __init__(self, problem: Problem):
        super().__init__(problem)

        self.z: LpVariable = LpVariable(name="Z")
        self.z_names: List[str] = []

    def _create_vars_z(self):
        """Creates the Z variables for the linear programming algorithm. Each
        Z_aeik is a binary variable. It is a indicator variable that is 0 if
        Y_aeik is 0, or 1 if Y_aeik is greater than 0."""
        for a in self.problem.system.apps:
            for e in self.problem.regions:
                for i in self.problem.system.ics:
                    for k in range(self.problem.workload_len):
                        if self._can_send_requests(e, i.region):
                            z_name = EdaropAllocator._aeik_name(a, e, i, k)
                            self.z_names.append(z_name)

        self.z = LpVariable.dicts(name="Z", indices=self.z_names, cat=LpBinary)

    def _create_vars(self):
        """Creates the variables for the linear programming algorithm. It adds
        the Z variables required for cost optimization."""
        super()._create_vars()

        self._create_vars_z()
        logging.info("There are %s Z variables", len(self.z))

    def _create_objective(self):
        """Adds the cost function to optimize."""
        self.lp_problem += lpSum(
            self.x[x_name] * self.x_info[x_name].price_per_ts for x_name in self.x_names
        )

    def _create_contraints_response_time(self):
        """If there are requests served from a region to an edge region e (i.e.,
        if Y_aeik > 0), the response time (n_er_i + S_ia) has to be equal to or
        less than the response time requirement (Ra)."""
        M = 1_000_000_000  # Big number, greater than max Y_aeik
        for a in self.problem.system.apps:
            for e in self.problem.regions:
                for i in self.problem.system.ics:
                    for k in range(self.problem.workload_len):
                        if not self._can_send_requests(e, i.region):
                            continue

                        aeik_name = EdaropAllocator._aeik_name(a, e, i, k)

                        self.lp_problem += self.y[aeik_name] <= M * self.z[aeik_name]

                        latency = self.problem.system.latencies[e, i.region]

                        # "_lu" means in latency units
                        perf = self.problem.system.perfs[a, i]
                        slo_lu = perf.slo.to(latency.value.units)

                        max_resp_time_lu = a.max_resp_time.to(latency.value.units)

                        self.lp_problem += (
                            self.z[aeik_name] * (latency.value.value + slo_lu)
                            <= max_resp_time_lu,
                            f"The response time for app {a.name} from region"
                            f" {e.name} to ic {i.name}"
                            f" ({latency.value.value + slo_lu}) in time slot {k} has"
                            f" to be equal to or less than R_a"
                            f" ({max_resp_time_lu})",
                        )

    def _create_contraints(self):
        """Adds the contraints. A response time constraint is added to the
        common constraints of edge architecture optimizations."""
        super()._create_contraints()
        self._create_contraints_response_time()


class EdaropRAllocator(EdaropAllocator):
    """This class receives a response time optimization problem for an edge
    architecture and gives methods to solve it and store the solution."""

    def __calculate_resp_time_sec(self, y_name) -> float:
        """Returns the response time in seconds."""
        e = self.y_info[y_name].region
        ic = self.y_info[y_name].ic
        app = self.y_info[y_name].app

        tresp = self.problem.system.tresp(app=app, region=e, ic=ic).to(TimeUnit("s"))
        return tresp * self.y[y_name]

    def _create_objective(self):
        """Adds the response time function to optimize. It is the average
        response time"""
        total_reqs = 0
        for a in self.problem.system.apps:
            for e in self.problem.regions:
                if (a, e) not in self.problem.workloads:
                    # Some apps might not have workload in a region
                    continue

                for k in range(self.problem.workload_len):
                    total_reqs += self.problem.workloads[(a, e)].values[k]
        self.lp_problem += (
            lpSum(self.__calculate_resp_time_sec(y_name) for y_name in self.y_names)
            / total_reqs
        )

    def _create_contraints_cost(self):
        """The total cost must be less than the maximum cost."""
        self.lp_problem += (
            lpSum(
                self.x[x_name] * self.x_info[x_name].price_per_ts
                for x_name in self.x_names
            )
            <= self.problem.max_cost,
            f"Total cost has to be less than {self.problem.max_cost}",
        )

    def _create_contraints(self):
        """Adds the contraints. A cost constraint is added to the common
        constraints of edge architecture optimizations."""
        super()._create_contraints()
        self._create_contraints_cost()
