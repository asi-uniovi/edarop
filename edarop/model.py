"""Classes for the model for edarop. Most of them are frozen data classes."""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, List, Dict, Optional
from typing_extensions import TypeAlias

from cloudmodel.unified.units import (
    Currency,
    CurrencyPerTime,
    Requests,
    RequestsPerTime,
    Time,
)

COST_UNDEFINED = Currency("-1 usd")
TIME_UNDEFINED = Time("-1 s")

# Type aliases
AllocationIcs: TypeAlias = Dict[Tuple["App", "InstanceClass"], int]
AllocationReqs: TypeAlias = Dict[Tuple["App", "Region", "InstanceClass"], int]


class Status(Enum):
    "Possible status of edarop solutions."
    UNSOLVED = 0
    OPTIMAL = 1
    INTEGER_FEASIBLE = 2
    INFEASIBLE = 3
    INTEGER_INFEASIBLE = 4
    OVERFULL = 5
    TRIVIAL = 6
    ABORTED = 7
    CBC_ERROR = 8
    UNKNOWN = 9


@dataclass(frozen=True)
class App:
    name: str
    max_resp_time: Time


@dataclass(frozen=True)
class Region:
    name: str


@dataclass(frozen=True)
class InstanceClass:
    name: str
    price: CurrencyPerTime
    region: Region


@dataclass(frozen=True)
class Workload:
    values: Tuple[Requests, ...]
    time_unit: Time


@dataclass(frozen=True)
class Latency:
    value: Time


@dataclass(frozen=True)
class Performance:
    value: RequestsPerTime
    slo: Time


@dataclass(frozen=True)
class System:
    apps: Tuple[App, ...]
    ics: Tuple[InstanceClass, ...]
    perfs: Dict[Tuple[App, InstanceClass], Performance]
    latencies: Dict[Tuple[Region, Region], Latency]  # src, dst -> latency

    def __post_init__(self):
        self.__check_uniq_names(self.apps, "apps")
        self.__check_uniq_names(self.ics, "instance classes")

        regions = list(ic.region for ic in self.ics)
        self.__check_uniq_names(regions, "regions")

    @staticmethod
    def __check_uniq_names(list_with_names, list_contents: str):
        """Checks that there are no two elements in a list that have the same
        field 'name' but are different objects."""
        for i in range(len(list_with_names)):
            for other in list_with_names[i + 1 :]:
                one = list_with_names[i]
                if one.name == other.name and id(one) != id(other):
                    raise ValueError(f"Repeated name {other.name} in {list_contents}")

    def resp_time(self, app: App, region: Region, ic: InstanceClass) -> Time:
        """Returns the response time for an app from a region using an instance
        class."""
        slo = self.perfs[(app, ic)].slo
        latency = self.latencies[(region, ic.region)].value
        return slo + latency


@dataclass(frozen=True)
class Problem:
    system: System
    workloads: Dict[Tuple[App, Region], Workload]
    max_cost: Currency = COST_UNDEFINED
    max_avg_resp_time: Time = TIME_UNDEFINED

    def __post_init__(self):
        self.__check_all_workloads_same_units()
        self.__check_all_workloads_same_len()

    def __check_all_workloads_same_units(self):
        if not self.workloads.values():
            return

        it = iter(self.workloads.values())
        units = next(it).time_unit
        if not all(w.time_unit == units for w in it):
            raise ValueError("Not all workloads have the same units")

    def __check_all_workloads_same_len(self):
        if not self.workloads.values():
            return

        it = iter(self.workloads.values())
        the_len = len(next(it).values)
        if not all(len(l.values) == the_len for l in it):
            raise ValueError("Not all workloads have the same length")

    @property
    def workload_len(self) -> int:
        """Returns the workload length in number of time slots taking the length
        from a workload."""
        a_workload = list(self.workloads.values())[0]
        return len(a_workload.values)

    @property
    def regions(self) -> Tuple[Region, ...]:
        """Returns any region found in any instance class or workload."""
        result = []
        for ic in self.system.ics:
            if ic.region not in result:
                result.append(ic.region)

        for wl_tuple in self.workloads.keys():
            if wl_tuple[1] not in result:
                result.append(wl_tuple[1])

        return tuple(result)

    @property
    def time_slot_unit(self):
        """Returns the time units of the time slot, taking it from a
        workload."""
        a_workload = list(self.workloads.values())[0]
        return a_workload.time_unit


@dataclass(frozen=True)
class TimeSlotAllocation:
    ics: AllocationIcs  # number of ICs per instance class
    reqs: AllocationReqs  # number of requests


@dataclass(frozen=True)
class Allocation:
    time_slot_allocs: List[TimeSlotAllocation]


@dataclass(frozen=True)
class SolvingStats:
    frac_gap: Optional[float]
    max_seconds: Optional[float]
    lower_bound: Optional[float]
    creation_time: float
    solving_time: float
    status: Status


@dataclass(frozen=True)
class Solution:
    problem: Problem
    alloc: Allocation
    solving_stats: SolvingStats
