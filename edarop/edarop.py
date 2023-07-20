"""Main module for the edarop package. It defines the base class
EdaropAllocator, which is the base class for two allocators: EdaropCAllocator,
which minimizes cost, and EdaropRAllocator, which minimizes response time. In
addition, there are three other allocators: EdaropCRAllocator, which minimizes
cost first and response time second, EdaropRCAllocator, which minimizes response
time first and cost second, and SimpleCostAllocator, which implements a greedy
algorithm.

All allocators receive an edarop problem and construct and solve the
corresponding linear programming problem using pulp."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
import time
import logging
from typing import Dict, List, Any
from functools import partial

import pulp  # type: ignore
from pulp import (  # type: ignore
    LpVariable,
    lpSum,
    LpProblem,
    LpMinimize,
    value,
    LpStatus,
    PulpSolverError,
    COIN_CMD,
    constants,
    subprocess,
    devnull,
    log,
    warnings,
    operating_system,
)
from pulp.constants import LpInteger, LpBinary  # type: ignore

from .model import (
    Problem,
    Solution,
    InstanceClass,
    App,
    Region,
    Allocation,
    TimeSlotAllocation,
    Status,
    SolvingStats,
    COST_UNDEFINED,
    TIME_UNDEFINED,
)

from .analysis import SolutionAnalyzer


def pulp_to_edarop_status(
    pulp_problem_status: int, pulp_solution_status: int
) -> Status:
    """Receives the PuLP status code for the problem (LpProblem.status) and the
    solution (LpProblem.sol_status) and returns a edarop Status."""
    if pulp_problem_status == pulp.LpStatusInfeasible:
        r = Status.INFEASIBLE
    elif pulp_problem_status == pulp.LpStatusNotSolved:
        r = Status.ABORTED
    elif pulp_problem_status == pulp.LpStatusOptimal:
        if pulp_solution_status == pulp.LpSolutionOptimal:
            r = Status.OPTIMAL
        else:
            r = Status.INTEGER_FEASIBLE
    elif pulp_problem_status == pulp.LpStatusUndefined:
        r = Status.INTEGER_INFEASIBLE
    else:
        r = Status.UNKNOWN
    return r


@dataclass
class XVarInfo:
    """Stores information about the app, instance class and time slot for an
    X variable. The price and performance is stored using as time unit one time
    slot."""

    app: App
    ic: InstanceClass
    time_slot: int
    price_per_ts: float  # usd per time slot
    perf_per_ts: float  # reqs per time slot


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
        self.x_names_app_timeslot: Dict[
            tuple(App, int), list[str]
        ] = {}  # Cache for x_names per app and time slot

        self.y: LpVariable = LpVariable(name="Y")
        self.y_names: List[str] = []
        self.y_info: Dict[str, YVarInfo] = {}  # The string is the var name
        self.y_names_app_ic_timeslot: Dict[
            tuple(App, InstanceClass, int), list[str]
        ] = {}  # Cache for y_names per app, ic and time slot
        self.y_names_app_region_timeslot: Dict[
            tuple(App, Region, int), list[str]
        ] = {}  # Cache for y_names per app, region and time slot

        self.z: LpVariable = LpVariable(name="Z")
        self.z_names: List[str] = []

    def solve(self, solver: Any = None) -> Solution:
        """Solve the linear programming problem and return the solution. A
        solver with options can be passed. For instance:

            from pulp import PULP_CBC_CMD
            solver = PULP_CBC_CMD(timeLimit=10, gapRel=0.01, threads=8, options=["preprocess off"])
        """
        start_creation = time.perf_counter()
        self._create_vars()
        self._create_objective()
        self._create_contraints()
        creation_time = time.perf_counter() - start_creation

        solving_stats = self.__solve_problem(solver, creation_time)

        return self._compose_solution(solving_stats)

    def __solve_problem(self, solver: Any, creation_time: float) -> SolvingStats:
        status = Status.UNKNOWN
        lower_bound = None

        start_solving = time.perf_counter()

        if solver is None:
            frac_gap = None
            max_seconds = None
        else:
            if "gapRel" in solver.optionsDict:
                frac_gap = solver.optionsDict["gapRel"]
            else:
                frac_gap = None
            max_seconds = solver.timeLimit

        try:
            self.lp_problem.solve(solver)
        except PulpSolverError as exception:
            end_solving = time.perf_counter()
            solving_time = end_solving - start_solving
            status = Status.CBC_ERROR

            print(
                f"Exception PulpSolverError. Time to failure: {solving_time} seconds",
                exception,
            )
        else:
            # No exceptions
            end_solving = time.perf_counter()
            solving_time = time.perf_counter() - start_solving
            status = pulp_to_edarop_status(
                self.lp_problem.status, self.lp_problem.sol_status
            )

        if status == Status.INTEGER_FEASIBLE:
            lower_bound = self.lp_problem.bestBound

        solving_stats = SolvingStats(
            frac_gap=frac_gap,
            max_seconds=max_seconds,
            lower_bound=lower_bound,
            creation_time=creation_time,
            solving_time=solving_time,
            status=status,
        )

        return solving_stats

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
                    perf_per_ts = perf.value.to(f"req / ({ts_unit})").magnitude

                    price_per_ts = i.price.to(f"usd / ({ts_unit})").magnitude
                    self.x_info[x_name] = XVarInfo(
                        app=a,
                        ic=i,
                        time_slot=k,
                        price_per_ts=price_per_ts,
                        perf_per_ts=perf_per_ts,
                    )

                    if (a, k) not in self.x_names_app_timeslot:
                        self.x_names_app_timeslot[a, k] = [x_name]
                    else:
                        self.x_names_app_timeslot[a, k].append(x_name)

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

                            if (a, i, k) not in self.y_names_app_ic_timeslot:
                                self.y_names_app_ic_timeslot[a, i, k] = [y_name]
                            else:
                                self.y_names_app_ic_timeslot[a, i, k].append(y_name)

                            if (a, e, k) not in self.y_names_app_region_timeslot:
                                self.y_names_app_region_timeslot[a, e, k] = [y_name]
                            else:
                                self.y_names_app_region_timeslot[a, e, k].append(y_name)

        self.y = LpVariable.dicts(
            name="Y", indices=self.y_names, lowBound=0, cat=LpInteger
        )

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
        """Creates the variables for the linear programming algorithm."""
        self._create_vars_x()
        self._create_vars_y()
        self._create_vars_z()

        logging.info("There are %s X variables", len(self.x))
        logging.info("There are %s Y variables", len(self.y))
        logging.info("There are %s Z variables", len(self.z))

    @abstractmethod
    def _create_objective(self) -> None:
        """Adds the function to optimize."""

    def _workload_for_app_in_time_slot(self, a: App, k: int) -> float:
        """Returns the workload for app a at time slot k for any region."""
        l_ak = 0.0
        for r in self.problem.regions:
            if (a, r) in self.problem.workloads:
                l_ak += self.problem.workloads[(a, r)].values[k].magnitude

        return l_ak

    def _create_contraints_throughput_per_app(self):
        """Adds throughput contraints per app and time slot: the performance
        of all the VMs for an app at a time slot has to be equal to or greater
        than the workload for that app at that time slot."""
        for a in self.problem.system.apps:
            for k in range(self.problem.workload_len):
                x_names = self.x_names_app_timeslot[a, k]

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

                    y_names = self.y_names_app_ic_timeslot[a, i, k]

                    x_name = EdaropAllocator._aik_name(a, i, k)

                    total_x_perf = self.x[x_name] * self.x_info[x_name].perf_per_ts

                    self.lp_problem += (
                        total_x_perf >= lpSum(self.y[y_name] for y_name in y_names),
                        f"The performance of ic {i.name} for app {a.name}"
                        f" in time slot {k} has to be greater than or equal"
                        f" to the number of requests assigned to it",
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
                    l_aek = self.problem.workloads[(a, e)].values[k].magnitude

                    if (a, e, k) not in self.y_names_app_region_timeslot:
                        continue
                    y_names = self.y_names_app_region_timeslot[a, e, k]

                    self.lp_problem += (
                        lpSum(self.y[y_name] for y_name in y_names) == l_aek,
                        f"The sum of requests for app {a.name} in time slot {k} from"
                        f" region {e.name} has to be equal to the workload ({l_aek})",
                    )

    def _create_contraints_response_time(self):
        """If there are requests served from a region to an edge region e (i.e.,
        if Y_aeik > 0), the response time (n_er_i + S_ia) has to be equal to or
        less than the response time requirement (R_a)."""
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

                        max_resp_time_lu = a.max_resp_time.to(
                            latency.value.units
                        ).magnitude

                        self.lp_problem += (
                            self.z[aeik_name]
                            * (latency.value.magnitude + slo_lu.magnitude)
                            <= max_resp_time_lu,
                            f"The response time for app {a.name} from region"
                            f" {e.name} to ic {i.name}"
                            f" ({latency.value.magnitude + slo_lu.magnitude}) in time slot {k} has"
                            f" to be equal to or less than R_a"
                            f" ({max_resp_time_lu})",
                        )

    def _create_contraints(self):
        """Adds the contraints."""
        self._create_contraints_throughput_per_app()
        self._create_contraints_throughput_per_ic()
        self._create_constraints_throughput_per_region()
        self._create_contraints_response_time()

    def _can_send_requests(self, src: Region, dst: Region) -> bool:
        """Returns true if requests can be sent from src to dst. It assumes that
        if there is latency data, it is possible."""
        return (src, dst) in self.problem.system.latencies

    def _calculate_resp_time_sec(self, y_name: str) -> float:
        """Returns the response time in seconds for an app in an ic in a
        region."""
        e = self.y_info[y_name].region
        ic = self.y_info[y_name].ic
        app = self.y_info[y_name].app

        resp_time = self.problem.system.resp_time(app=app, region=e, ic=ic)
        resp_time_sec = resp_time.to("1s").magnitude
        return resp_time_sec * self.y[y_name]

    def _get_total_reqs(self) -> int:
        """Returns the total number of requests in the workload."""
        total_reqs: int = 0
        for a in self.problem.system.apps:
            for e in self.problem.regions:
                if (a, e) not in self.problem.workloads:
                    # Some apps might not have workload in a region
                    continue

                for k in range(self.problem.workload_len):
                    total_reqs += self.problem.workloads[(a, e)].values[k].magnitude

        return total_reqs

    def _get_valid_reqs(self, aeik_name: str) -> int:
        """Returns the number of requests for an app a from a region e in an ic
        i in a time slot k. It fixes a bug in the solver that returns a very
        small value for some variables."""
        reqs = self.y[aeik_name].value()

        if abs(reqs) < 1e-7:
            return 0  # This is a very small value, so we consider it 0

        if reqs > 0:
            return reqs  # This is OK

        # This is a big negative value, so we raise an exception
        raise ValueError(f"Invalid value for requests in {aeik_name}: {reqs}")

    def _get_alloc(self, time_slot: int) -> TimeSlotAllocation:
        """Returns the allocation for a time slot."""
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
                        reqs[a, r, i] = self._get_valid_reqs(aeik_name)

        return TimeSlotAllocation(ics, reqs)

    def _compose_solution(self, solving_stats: SolvingStats) -> Solution:
        self._log_solution()

        if solving_stats.status not in [Status.OPTIMAL, Status.INTEGER_FEASIBLE]:
            alloc = Allocation(time_slot_allocs=[])
        else:
            alloc = Allocation(
                time_slot_allocs=[
                    self._get_alloc(k) for k in range(self.problem.workload_len)
                ]
            )

        return Solution(problem=self.problem, alloc=alloc, solving_stats=solving_stats)

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
        EdaropAllocator._log_var(self.z)

        logging.info("Status: %s", LpStatus[self.lp_problem.status])
        logging.info("Objective: %f", value(self.lp_problem.objective))


class EdaropCAllocator(EdaropAllocator):
    """This class receives a cost optimization problem for an edge architecture
    and gives methods to solve it and store the solution."""

    def _create_objective(self):
        """Adds the cost function to optimize."""
        self.lp_problem += lpSum(
            self.x[x_name] * self.x_info[x_name].price_per_ts for x_name in self.x_names
        )

    def _create_constraint_max_avg_resp_time(self):
        """Creates a constraint for the maximum average response time."""
        max_resp_time_sec = self.problem.max_avg_resp_time.to("s").magnitude
        self.lp_problem += (
            lpSum(self._calculate_resp_time_sec(y_name) for y_name in self.y_names)
            / self._get_total_reqs()
            <= max_resp_time_sec,
            f"Max. average response time has to be equal to or less than "
            f"{self.problem.max_avg_resp_time}",
        )

    def _create_contraints(self):
        """Adds the contraints. A max average response time constraint is added
        to the common constraints of edge architecture optimizations if it is
        defined in the problem."""
        super()._create_contraints()

        if self.problem.max_avg_resp_time != TIME_UNDEFINED:
            self._create_constraint_max_avg_resp_time()


class EdaropRAllocator(EdaropAllocator):
    """This class receives a response time optimization problem for an edge
    architecture and gives methods to solve it and store the solution."""

    def _create_objective(self):
        """Adds the response time function to optimize. It is the average
        response time."""
        self.lp_problem += (
            lpSum(self._calculate_resp_time_sec(y_name) for y_name in self.y_names)
            / self._get_total_reqs()
        )

    def _create_contraints_cost(self):
        """The total cost must be less than the maximum cost."""
        if self.problem.max_cost == COST_UNDEFINED:
            raise ValueError("The maximum cost in the problem is not initialized")

        self.lp_problem += (
            lpSum(
                self.x[x_name] * self.x_info[x_name].price_per_ts
                for x_name in self.x_names
            )
            <= self.problem.max_cost.magnitude,
            f"Total cost has to be equal to or less than {self.problem.max_cost}",
        )

    def _create_contraints(self):
        """Adds the contraints. A cost constraint is added to the common
        constraints of edge architecture optimizations."""
        super()._create_contraints()
        self._create_contraints_cost()


class EdaropCRAllocator:
    """This class receives a multi-objective optimization problem for an edge
    architecture and gives methods to solve it and store the solution. First,
    the minimum cost is obtained without minimizing the average response time
    and, then, the minimum average response time is obtained for the cost
    previously computed."""

    def __init__(self, problem: Problem):
        """Constructor.

        Args:
            problem: problem to solve."""
        self.problem = problem

    def solve(self, solver: Any = None) -> Solution:
        """Solve the linear programming problem and return the solution."""
        edarop_c = EdaropCAllocator(self.problem)
        sol_c = edarop_c.solve(solver)

        optimal_cost = SolutionAnalyzer(sol_c).cost()

        new_problem = Problem(
            system=self.problem.system,
            workloads=self.problem.workloads,
            max_cost=optimal_cost,
        )
        edarop_r = EdaropRAllocator(new_problem)
        sol_r = edarop_r.solve(solver)

        # Compose a new solution from sol_r but with the solving stats including
        # the creation and solving times of both sol_r and sol_c. The rest of
        # the stats are taken from sol_r.
        stats_r = sol_r.solving_stats

        combined_solving_stats = SolvingStats(
            frac_gap=stats_r.frac_gap,
            max_seconds=stats_r.max_seconds,
            lower_bound=stats_r.lower_bound,
            creation_time=stats_r.creation_time + sol_c.solving_stats.creation_time,
            solving_time=stats_r.solving_time + sol_c.solving_stats.solving_time,
            status=stats_r.status,
        )

        sol_rc = Solution(
            problem=sol_r.problem,
            alloc=sol_r.alloc,
            solving_stats=combined_solving_stats,
        )

        return sol_rc


class EdaropRCAllocator:
    """This class receives a multi-objective optimization problem for an edge
    architecture and gives methods to solve it and store the solution. First,
    the minimum average response time is obtained without minimizing the cost
    and, then, the minimum cost is obtained for the average response time
    previously computed."""

    def __init__(self, problem: Problem):
        """Constructor.

        Args:
            problem: problem to solve."""
        self.problem = problem

    def solve(self, solver: Any = None) -> Solution:
        """Solve the linear programming problem and return the solution."""
        edarop_r = EdaropRAllocator(self.problem)
        sol_r = edarop_r.solve(solver)

        optimal_resp_time = SolutionAnalyzer(sol_r).avg_resp_time()

        new_problem = Problem(
            system=self.problem.system,
            workloads=self.problem.workloads,
            max_cost=self.problem.max_cost,
            max_avg_resp_time=optimal_resp_time,
        )
        edarop_c = EdaropCAllocator(new_problem)
        sol_c = edarop_c.solve(solver)

        # Compose a new solution from sol_c but with the solving stats including
        # the creation and solving times of both sol_r and sol_c. The rest of
        # the stats are taken from sol_c.
        stats_c = sol_c.solving_stats

        combined_solving_stats = SolvingStats(
            frac_gap=stats_c.frac_gap,
            max_seconds=stats_c.max_seconds,
            lower_bound=stats_c.lower_bound,
            creation_time=sol_r.solving_stats.creation_time + stats_c.creation_time,
            solving_time=sol_r.solving_stats.solving_time + stats_c.solving_time,
            status=stats_c.status,
        )

        sol_cr = Solution(
            problem=sol_c.problem,
            alloc=sol_c.alloc,
            solving_stats=combined_solving_stats,
        )

        return sol_cr


# pylint: disable = E, W, R, C
def _solve_CBC_patched(self, lp, use_mps=True):
    """Solve a MIP problem using CBC patched from original PuLP function
    to save a log with cbc's output and take from it the best bound."""

    def take_best_bound_from_log(filename, msg: bool):
        ret = None
        try:
            with open(filename, "r", encoding="utf8") as f:
                for l in f:
                    if msg:
                        print(l, end="")
                    if l.startswith("Lower bound:"):
                        ret = float(l.split(":")[-1])
        except:
            pass
        return ret

    if not self.executable(self.path):
        raise PulpSolverError(
            "Pulp: cannot execute %s cwd: %s" % (self.path, os.getcwd())
        )
    tmpLp, tmpMps, tmpSol, tmpMst = self.create_tmp_files(
        lp.name, "lp", "mps", "sol", "mst"
    )
    if use_mps:
        vs, variablesNames, constraintsNames, _ = lp.writeMPS(tmpMps, rename=1)
        cmds = " " + tmpMps + " "
        if lp.sense == constants.LpMaximize:
            cmds += "max "
    else:
        vs = lp.writeLP(tmpLp)
        # In the Lp we do not create new variable or constraint names:
        variablesNames = dict((v.name, v.name) for v in vs)
        constraintsNames = dict((c, c) for c in lp.constraints)
        cmds = " " + tmpLp + " "
    if self.optionsDict.get("warmStart", False):
        self.writesol(tmpMst, lp, vs, variablesNames, constraintsNames)
        cmds += "mips {} ".format(tmpMst)
    if self.timeLimit is not None:
        cmds += "sec %s " % self.timeLimit
    options = self.options + self.getOptions()
    for option in options:
        cmds += option + " "
    if self.mip:
        cmds += "branch "
    else:
        cmds += "initialSolve "
    cmds += "printingOptions all "
    cmds += "solution " + tmpSol + " "
    if self.msg:
        pipe = subprocess.PIPE  # Modified
    else:
        pipe = open(os.devnull, "w")
    logPath = self.optionsDict.get("logPath")
    if logPath:
        if self.msg:
            warnings.warn(
                "`logPath` argument replaces `msg=1`. The output will be redirected to the log file."
            )
        pipe = open(self.optionsDict["logPath"], "w")
    log.debug(self.path + cmds)
    args = []
    args.append(self.path)
    args.extend(cmds[1:].split())
    with open(tmpLp + ".log", "w", encoding="utf8") as pipe:
        print(f"You can check the CBC log at {tmpLp}.log", flush=True)
        if not self.msg and operating_system == "win":
            # Prevent flashing windows if used from a GUI application
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            cbc = subprocess.Popen(
                args, stdout=pipe, stderr=pipe, stdin=devnull, startupinfo=startupinfo
            )
        else:
            cbc = subprocess.Popen(args, stdout=pipe, stderr=pipe, stdin=devnull)

        # Modified to get the best bound
        # output, _ = cbc.communicate()
        # if pipe:
        #     print("CBC output")
        #     for line in StringIO(output.decode("utf8")):
        #         if line.startswith("Lower bound:"):
        #             lp.bestBound = float(line.split(":")[1].strip())

        #         print(line, end="")

        if cbc.wait() != 0:
            if pipe:
                pipe.close()
            raise PulpSolverError(
                "Pulp: Error while trying to execute, use msg=True for more details"
                + self.path
            )
        if pipe:
            pipe.close()
    if not os.path.exists(tmpSol):
        raise PulpSolverError("Pulp: Error while executing " + self.path)
    (
        status,
        values,
        reducedCosts,
        shadowPrices,
        slacks,
        sol_status,
    ) = self.readsol_MPS(tmpSol, lp, vs, variablesNames, constraintsNames)
    lp.assignVarsVals(values)
    lp.assignVarsDj(reducedCosts)
    lp.assignConsPi(shadowPrices)
    lp.assignConsSlack(slacks, activity=True)
    lp.assignStatus(status, sol_status)
    lp.bestBound = take_best_bound_from_log(tmpLp + ".log", self.msg)
    self.delete_tmp_files(tmpMps, tmpLp, tmpSol, tmpMst)
    return status


# Monkey patching
COIN_CMD.solve_CBC = _solve_CBC_patched
