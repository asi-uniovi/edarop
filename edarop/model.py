"""Classes for the model for edarop. Most of them are frozen data classes."""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, List, Dict, Optional
from typing_extensions import TypeAlias

# Type aliases
AllocationIcs: TypeAlias = Dict[Tuple["App", "InstanceClass"], int]
AllocationReqs: TypeAlias = Dict[Tuple["App", "Region", "InstanceClass"], int]


class TimeUnit:
    """Provides a simple method to perform time units conversions.
    It stores as a class attribute a dictionary whose keys are strings representing the time units
    (eg: "h", "m", "s") and the values are the factor to convert one into another.
    The value for "s" is 1, for "m" it would be 60, etc.
    Inheritance can be used to extend the known time units. You have however to rewrite the
    whole dictionary plus the new units in the derived class."""

    conversion_factors = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 24 * 60 * 60,
        "y": 365 * 24 * 60 * 60,
    }

    def __init__(self, unit: str, amount: float = 1) -> None:
        """Creates a TimeUnit for the given unit.
        Args:
            unit: The string representing the time unit, e.g. "h" for hours
            amount: Amount of time units, defaults to 1.
        Raises:
            ValueError: if the string does not represent a known time unit.
        """
        self.check_valid_unit(unit)
        self.unit = unit
        self.amount = amount

    def to(self, to_unit) -> float:
        """Convert this time unit into a different time unit.
        Args:
            to_unit: string representing the time unit to which convert, e.g. "s" for seconds
        Returns:
            The number of units of type "to_unit" in the time "self.unit". For example,
            TimeUnit("h").to("s") will return 3600.
        Raises:
            ValueError if "to_unit" is not a known time unit.
        """
        self.check_valid_unit(to_unit)
        return (
            self.amount
            * self.conversion_factors[self.unit]
            / self.conversion_factors[to_unit]
        )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __hash__(self):
        return id(self)

    def __repr__(self):
        return f"{self.amount} {self.unit}"

    @classmethod
    def check_valid_unit(cls, unit):
        """Checks the validity of the time unit, by looking it up in the keys of
        the class attribute conversion_factors. Note that this allows for using inheritance
        to extend the list of known time units."""
        if unit not in cls.conversion_factors.keys():
            raise ValueError(
                "Unit {} is not valid. Use one of {}".format(
                    repr(unit), list(cls.conversion_factors.keys())
                )
            )


@dataclass(frozen=True)
class TimeValue:
    value: float
    units: TimeUnit

    def to(self, time_unit: TimeUnit) -> float:
        """Converts to time_unit."""
        return self.value * self.units.to(time_unit.unit)

    def __repr__(self):
        return f"{self.value} x {self.units}"


@dataclass(frozen=True)
class TimeRatioValue:
    value: float
    units: TimeUnit

    def to(self, time_unit: TimeUnit) -> float:
        """Converts to time_unit."""
        return self.value / self.units.to(time_unit.unit)

    def __repr__(self):
        return f"{self.value} per {self.units}"


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
    max_resp_time: TimeValue


@dataclass(frozen=True)
class Region:
    name: str


@dataclass(frozen=True)
class InstanceClass:
    name: str
    price: TimeRatioValue
    region: Region


@dataclass(frozen=True)
class Workload:
    values: Tuple[int, ...]
    time_unit: TimeUnit


@dataclass(frozen=True)
class Latency:
    value: TimeValue


@dataclass(frozen=True)
class Performance:
    value: TimeRatioValue
    slo: TimeValue


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

    def resp_time(self, app: App, region: Region, ic: InstanceClass) -> TimeValue:
        """Returns the response time for an app from a region using an instance
        class."""
        slo = self.perfs[(app, ic)].slo.to(TimeUnit("s"))
        latency = self.latencies[(region, ic.region)].value.to(TimeUnit("s"))
        return TimeValue(slo + latency, TimeUnit("s"))


@dataclass(frozen=True)
class Problem:
    system: System
    workloads: Dict[Tuple[App, Region], Workload]
    max_cost: float = -1
    max_avg_resp_time: TimeValue = TimeValue(-1, TimeUnit("s"))

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
