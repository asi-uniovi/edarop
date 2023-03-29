Edarop
======

![Testing status](https://github.com/asi-uniovi/edarop/actions/workflows/tests.yaml/badge.svg)

Edge architecture optimizator. Use linear programming to allocate applications
to edge infrastructure optimizing cost and response time.

Introduction
------------

Edarop is a Python package to solve allocation problems in Infrastructure as a
Service (IaaS) edge arquitectures. The objective is to optimize the cost and the
respose time from the point of view of the cloud customer. It is assumed that
there is a set of time slots where the allocated VMs do not change.

One of the basic concepts is the `Region` class, which represents a geographical
area where the users or the VMs are located. There is latency matrix between
regions, which is used to compute the maximum response time of a request.
Another parameter required to compute this maximum response time is the maximum
service time of each application in each VM. VMs are grouped in `InstanceClass`
objects, which represent a set of VMs with the same characteristics (region,
price and performance).

Inputs:

- A set of regions.
- A latency matrix between regions. If there is no latency between two regions,
  it is assumed that there can be no communication between them.
- A set of applications.
- A set of instance classes (VM types).
- The performance of each instance class for each application.
- The workload of each application for each time slot.

All the inputs are represented by objects of the classes in the `edarop` module
and are collected in a `Problem` object, which aggregates a `System` object and
a dictionary of `Workload` objects, in addition to two optional values to fix a
maximum cost and average of the maximum response time.

Outputs:

- The allocation for each time slot as part of a `Solution` object, which also
  includes a copy of the problem and some statistics about the solution.
  
An allocation indicates for each time slot how many VMs of each instance class
should be allocated for each application in the `ics` field. It also indicates,
in the `reqs` field, how many requests of each application should be allocated
to each instance class depending on the application and source region of the
request.

Installation
------------

Clone the repository:

```bash
git clone https://github.com/asi-uniovi/edarop.git
cd edarop
```

Optionally, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the package with `pip`:

```bash
pip install .
```

If you want to be able to modify the code and see the changes reflected in the
package, install it in editable mode:

```bash
pip install -e .
```

Usage
-----

You can see [an example](examples/example1.py) of usage in the
[`examples`](examples) folder. You can run it with:

```bash
python examples/example.py
```

You will see the output of the solver at the end.

If you want to use the package in your own code, import the required classes:

```python
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
```

Create the objects that represent the system, the workload and the problem:

```python
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
```

The last line prints some tables with the problem data. The output is:

```
           Regions and instance classes           
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Region   ┃ Instance class      ┃ Price         ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ eu-cloud │ c5.2xlarge-eu-cloud │ 0.388 per 1 h │
│          │ c5.4xlarge-eu-cloud │ 0.776 per 1 h │
├──────────┼─────────────────────┼───────────────┤
│ eu-edge  │ c5.2xlarge-eu-edge  │ 0.524 per 1 h │
├──────────┼─────────────────────┼───────────────┤
│ us-cloud │ c5.2xlarge-us-cloud │ 0.34 per 1 h  │
│          │ c5.4xlarge-us-cloud │ 0.68 per 1 h  │
├──────────┼─────────────────────┼───────────────┤
│ us-edge  │ c5d.2xlarge-us-edge │ 0.48 per 1 h  │
└──────────┴─────────────────────┴───────────────┘
                            Apps                            
┏━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name ┃ Max. resp. time. ┃ Workload (2 time slots of 1 h) ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ a0   │ 0.04 x 1 s       │ total: 8_139_600               │
│      │                  │   eu-user: 7_174_800           │
│      │                  │   us-user: 964_800             │
├──────┼──────────────────┼────────────────────────────────┤
│ a1   │ 0.325 x 1 s      │ total: 705_600                 │
│      │                  │   eu-user: 306_000             │
│      │                  │   us-user: 399_600             │
└──────┴──────────────────┴────────────────────────────────┘
                              Latencies (ms)                               
┏━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ src / dst ┃ eu-cloud ┃ eu-edge ┃ us-cloud ┃ us-edge ┃ eu-user ┃ us-user ┃
┡━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│ eu-user   │ 16.20    │ 8.72    │ 106.90   │ -       │ -       │ -       │
│ us-user   │ 105.80   │ -       │ 14.00    │ 1.10    │ -       │ -       │
└───────────┴──────────┴─────────┴──────────┴─────────┴─────────┴─────────┘
                                        Performances                                         
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Instance class                 ┃ App ┃ RPS     ┃ Max. resp. time ┃ Price per million req. ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│ c5.2xlarge-eu-cloud - eu-cloud │ a0  │ 461.125 │ 0.025 x 1 s     │ 0.23                   │
│                                │ a1  │ 76.796  │ 0.0125 x 1 s    │ 1.40                   │
├────────────────────────────────┼─────┼─────────┼─────────────────┼────────────────────────┤
│ c5.4xlarge-eu-cloud - eu-cloud │ a0  │ 919.905 │ 0.025 x 1 s     │ 0.23                   │
│                                │ a1  │ 153.005 │ 0.0125 x 1 s    │ 1.41                   │
├────────────────────────────────┼─────┼─────────┼─────────────────┼────────────────────────┤
│ c5.2xlarge-eu-edge - eu-edge   │ a0  │ 461.125 │ 0.025 x 1 s     │ 0.32                   │
│                                │ a1  │ 76.796  │ 0.0125 x 1 s    │ 1.90                   │
├────────────────────────────────┼─────┼─────────┼─────────────────┼────────────────────────┤
│ c5.2xlarge-us-cloud - us-cloud │ a0  │ 461.125 │ 0.025 x 1 s     │ 0.20                   │
│                                │ a1  │ 76.796  │ 0.0125 x 1 s    │ 1.23                   │
├────────────────────────────────┼─────┼─────────┼─────────────────┼────────────────────────┤
│ c5.4xlarge-us-cloud - us-cloud │ a0  │ 919.905 │ 0.025 x 1 s     │ 0.21                   │
│                                │ a1  │ 153.005 │ 0.0125 x 1 s    │ 1.23                   │
├────────────────────────────────┼─────┼─────────┼─────────────────┼────────────────────────┤
│ c5d.2xlarge-us-edge - us-edge  │ a0  │ 449.114 │ 0.025 x 1 s     │ 0.30                   │
│                                │ a1  │ 80.296  │ 0.0125 x 1 s    │ 1.66                   │
└────────────────────────────────┴─────┴─────────┴─────────────────┴────────────────────────┘
```

Finally, create an allocator and solve the problem:

```python
solver = PULP_CBC_CMD(msg=True, timeLimit=120, options=["preprocess off"])
sol_cr = EdaropCRAllocator(problem).solve(solver)

sol_pretty_printer = SolutionPrettyPrinter(sol_cr)
sol_pretty_printer.get_summary()
sol_pretty_printer.print()
```

`EdaropCRAllocator` is an allocator that minizes the cost first and the
average of the maximum response time second. There are other allocators:

- `EdaropCAllocator`: minimizes the cost.
- `EdaropRAllocator`: minimizes the average of the maximum response time.
- `EdaropCRAllocator`: minimizes the cost first and the average of the maximum
  response time second.
- `SimpleAllocator`: implements a greedy algorithm.

The `solve` method takes an optional solver parameter that can be used to set
some solver parameters.

The `SolutionPrettyPrinter` class can be used to print the solution in a nice
way. This is the result of the previous example:

```
                     Application a0 - max. resp. time: 0.04 x 1 s                     
┏━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ t     ┃ ic / src            ┃ num vms ┃ total cost ┃ num reqs  ┃ avg resp_time (s) ┃
┡━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ 0     │ c5.2xlarge-eu-edge  │ 3       │ 1.572      │           │                   │
│       │   eu-user           │         │            │ 3_600_000 │ 0.034             │
│       │ c5.2xlarge-us-cloud │ 1       │ 0.340      │           │                   │
│       │   us-user           │         │            │ 450_000   │ 0.039             │
├───────┼─────────────────────┼─────────┼────────────┼───────────┼───────────────────┤
│ total │                     │ 4       │ 1.91       │ 4_050_000 │ 0.03431           │
├───────┼─────────────────────┼─────────┼────────────┼───────────┼───────────────────┤
│ 1     │ c5.2xlarge-eu-edge  │ 3       │ 1.572      │           │                   │
│       │   eu-user           │         │            │ 3_574_800 │ 0.034             │
│       │ c5.2xlarge-us-cloud │ 1       │ 0.340      │           │                   │
│       │   us-user           │         │            │ 514_800   │ 0.039             │
├───────┼─────────────────────┼─────────┼────────────┼───────────┼───────────────────┤
│ total │                     │ 4       │ 1.91       │ 4_089_600 │ 0.03438           │
└───────┴─────────────────────┴─────────┴────────────┴───────────┴───────────────────┘
                    Application a1 - max. resp. time: 0.325 x 1 s                    
┏━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ t     ┃ ic / src            ┃ num vms ┃ total cost ┃ num reqs ┃ avg resp_time (s) ┃
┡━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ 0     │ c5.2xlarge-us-cloud │ 2       │ 0.680      │          │                   │
│       │   eu-user           │         │            │ 100_800  │ 0.119             │
│       │   us-user           │         │            │ 241_200  │ 0.027             │
├───────┼─────────────────────┼─────────┼────────────┼──────────┼───────────────────┤
│ total │                     │ 2       │ 0.68       │ 342_000  │ 0.05388           │
├───────┼─────────────────────┼─────────┼────────────┼──────────┼───────────────────┤
│ 1     │ c5.4xlarge-us-cloud │ 1       │ 0.680      │          │                   │
│       │   eu-user           │         │            │ 205_200  │ 0.119             │
│       │   us-user           │         │            │ 158_400  │ 0.027             │
├───────┼─────────────────────┼─────────┼────────────┼──────────┼───────────────────┤
│ total │                     │ 1       │ 0.68       │ 363_600  │ 0.07893           │
└───────┴─────────────────────┴─────────┴────────────┴──────────┴───────────────────┘

Total cost: 5.183999999999999 (max. cost: 5.183999999999999)
Average response time: 0.037 s
Deadline miss ratio: 0.000
```

Credits
-------

This package was created with
[Cookiecutter](https://github.com/audreyr/cookiecutter) and the
[`audreyr/cookiecutter-pypackage`](https://github.com/audreyr/cookiecutter-pypackage)
project template.
