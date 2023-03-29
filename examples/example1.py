"""This file shows an example of using edarop. It has two user regions, two edge
regions, and two cloud regions. There are two applications."""

from rich import print
from pulp import PULP_CBC_CMD  # type: ignore

from edarop.model import (
    Region,
    TimeUnit,
    TimeValue,
    InstanceClass,
    TimeRatioValue,
    App,
    Performance,
    Workload,
    System,
    Problem,
    Latency,
)
from edarop.edarop import EdaropCRAllocator
from edarop.visualization import SolutionPrettyPrinter, ProblemPrettyPrinter

# Prepare input data

# First, the regions. We put them in a list to make it easier to create a
# dictionary where the keys are the region names.
region_list = (
    Region("eu-user"),  # Hamburg
    Region("us-user"),  # Atlanta
    Region("eu-edge"),  # Hamburg
    Region("us-edge"),  # Atlanta
    Region("eu-cloud"),  # Frankfurt
    Region("us-cloud"),  # N. Virginia
)

regions = {i.name: i for i in region_list}


# Secondly, the latencies, taking into account that from an user region we can
# only go to the edge region nearby or to any cloud region. We only need the
# latencies from the user regions to the other regions.
latencies = {
    # eu-user
    (regions["eu-user"], regions["eu-edge"]): Latency(
        value=TimeValue(0.00872, TimeUnit("s")),
    ),
    (regions["eu-user"], regions["eu-cloud"]): Latency(
        value=TimeValue(0.0162, TimeUnit("s")),
    ),
    (regions["eu-user"], regions["us-cloud"]): Latency(
        value=TimeValue(0.1069, TimeUnit("s")),
    ),
    # us-user
    (regions["us-user"], regions["us-edge"]): Latency(
        value=TimeValue(0.0011, TimeUnit("s")),
    ),
    (regions["us-user"], regions["eu-cloud"]): Latency(
        value=TimeValue(0.1058, TimeUnit("s")),
    ),
    (regions["us-user"], regions["us-cloud"]): Latency(
        value=TimeValue(0.014, TimeUnit("s")),
    ),
}

# Thirly, instance classes. We put them in a list to make it easier to create a
# dictionary where the keys are the instance class names.
ic_list = (
    # eu-cloud
    InstanceClass(
        name="c5.2xlarge-eu-cloud",
        price=TimeRatioValue(0.388, TimeUnit("h")),
        region=regions["eu-cloud"],
    ),
    InstanceClass(
        name="c5.4xlarge-eu-cloud",
        price=TimeRatioValue(0.776, TimeUnit("h")),
        region=regions["eu-cloud"],
    ),
    # eu-edge
    InstanceClass(
        name="c5.2xlarge-eu-edge",
        price=TimeRatioValue(0.524, TimeUnit("h")),
        region=regions["eu-edge"],
    ),
    # us-cloud
    InstanceClass(
        name="c5.2xlarge-us-cloud",
        price=TimeRatioValue(0.34, TimeUnit("h")),
        region=regions["us-cloud"],
    ),
    InstanceClass(
        name="c5.4xlarge-us-cloud",
        price=TimeRatioValue(0.68, TimeUnit("h")),
        region=regions["us-cloud"],
    ),
    # us-edge
    InstanceClass(
        name="c5d.2xlarge-us-edge",
        price=TimeRatioValue(0.48, TimeUnit("h")),
        region=regions["us-edge"],
    ),
)

ics = {i.name: i for i in ic_list}

# Fourthly, the applications. We put them in a list to make it easier to create
# a dictionary where the keys are the application names.
app_list = (
    App(name="a0", max_resp_time=TimeValue(0.04, TimeUnit("s"))),
    App(name="a1", max_resp_time=TimeValue(0.325, TimeUnit("s"))),
)

apps = {a.name: a for a in app_list}

# The values are the performance (in rps) and the S_ia (in seconds).
# This is a shortcut for not having to repeat all units.
perf_dict = {
    # a0
    (apps["a0"], ics["c5.2xlarge-eu-cloud"]): (461.125, 0.025),
    (apps["a0"], ics["c5.4xlarge-eu-cloud"]): (919.905, 0.025),
    (apps["a0"], ics["c5.2xlarge-eu-edge"]): (461.125, 0.025),
    (apps["a0"], ics["c5.2xlarge-us-cloud"]): (461.125, 0.025),
    (apps["a0"], ics["c5.4xlarge-us-cloud"]): (919.905, 0.025),
    (apps["a0"], ics["c5d.2xlarge-us-edge"]): (449.114, 0.025),
    # a1
    (apps["a1"], ics["c5.2xlarge-eu-cloud"]): (76.796, 0.0125),
    (apps["a1"], ics["c5.4xlarge-eu-cloud"]): (153.005, 0.0125),
    (apps["a1"], ics["c5.2xlarge-eu-edge"]): (76.796, 0.0125),
    (apps["a1"], ics["c5.2xlarge-us-cloud"]): (76.796, 0.0125),
    (apps["a1"], ics["c5.4xlarge-us-cloud"]): (153.005, 0.0125),
    (apps["a1"], ics["c5d.2xlarge-us-edge"]): (80.296, 0.0125),
}

# Here, the dictionary required by the System class is created.
perfs = {}
for p, v in perf_dict.items():
    perfs[p] = Performance(
        value=TimeRatioValue(v[0], TimeUnit("s")),
        slo=TimeValue(v[1], TimeUnit("s")),
    )

# Finally, the system is created.
system = System(apps=app_list, ics=ic_list, perfs=perfs, latencies=latencies)

# The workloads are defined here. The values are the number of requests per
# hour. There are two time slots. We define the workloads for each application
# and user region.
workloads = {
    (apps["a0"], regions["eu-user"]): Workload(
        values=[1000 * 3600, 993 * 3600],
        time_unit=TimeUnit("h"),
    ),
    (apps["a1"], regions["eu-user"]): Workload(
        values=[28 * 3600, 57 * 3600],
        time_unit=TimeUnit("h"),
    ),
    (apps["a0"], regions["us-user"]): Workload(
        values=[125 * 3600, 143 * 3600],
        time_unit=TimeUnit("h"),
    ),
    (apps["a1"], regions["us-user"]): Workload(
        values=[67 * 3600, 44 * 3600],
        time_unit=TimeUnit("h"),
    ),
}

# Create problem
problem = Problem(system=system, workloads=workloads, max_cost=-1)

ProblemPrettyPrinter(problem).print()

# Solve

solver = PULP_CBC_CMD(msg=True, timeLimit=120, options=["preprocess off"])
sol_cr = EdaropCRAllocator(problem).solve(solver)

# Print solution

sol_pretty_printer = SolutionPrettyPrinter(sol_cr)
sol_pretty_printer.get_summary()
sol_pretty_printer.print()
