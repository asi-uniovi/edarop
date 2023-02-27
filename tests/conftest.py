"""Pytest configuration file for the edarop package."""
from typing import Tuple, Dict

import pytest

from edarop.model import (
    TimeUnit,
    TimeValue,
    TimeRatioValue,
    InstanceClass,
    Region,
    Workload,
    App,
    Latency,
    Performance,
    System,
)


@pytest.fixture(scope="module")
def system_wl_four_two_apps(
    request: pytest.FixtureRequest,
) -> Tuple[System, Dict[Tuple[App, Region], Workload]]:
    """Returns a system with four regions, eight instance classes, two apps, and
    the workload for each app in each region. The param in request is the
    maximum response time in seconds for app a0."""
    # Cloud regions
    region_ireland = Region("Ireland")
    region_hong_kong = Region("Honk Kong")

    # Edge regions
    region_dublin = Region("Dublin")
    region_madrid = Region("Madrid")

    latencies = {
        (region_dublin, region_ireland): Latency(
            value=TimeValue(0.05, TimeUnit("s")),
        ),
        (region_dublin, region_hong_kong): Latency(
            value=TimeValue(0.2, TimeUnit("s")),
        ),
        (region_dublin, region_dublin): Latency(
            value=TimeValue(0.04, TimeUnit("s")),
        ),
        (region_madrid, region_ireland): Latency(
            value=TimeValue(0.07, TimeUnit("s")),
        ),
        (region_madrid, region_hong_kong): Latency(
            value=TimeValue(0.21, TimeUnit("s")),
        ),
        (region_madrid, region_madrid): Latency(
            value=TimeValue(0.045, TimeUnit("s")),
        ),
    }

    ic_m5_xlarge_ireland = InstanceClass(
        name="m5.xlarge_ireland",
        price=TimeRatioValue(0.214, TimeUnit("h")),
        region=region_ireland,
    )
    ic_m5_2xlarge_ireland = InstanceClass(
        name="m5.2xlarge_ireland",
        price=TimeRatioValue(0.428, TimeUnit("h")),
        region=region_ireland,
    )

    ic_m5_xlarge_hong_kong = InstanceClass(
        name="m5.xlarge_hong_kong",
        price=TimeRatioValue(0.264, TimeUnit("h")),
        region=region_hong_kong,
    )
    ic_m5_2xlarge_hong_kong = InstanceClass(
        name="m5.2xlarge_hong_kong",
        price=TimeRatioValue(0.528, TimeUnit("h")),
        region=region_hong_kong,
    )

    c3_medium_madrid = InstanceClass(
        name="c3.medium_madrid",
        price=TimeRatioValue(1.65, TimeUnit("h")),
        region=region_madrid,
    )
    c3_medium_dublin = InstanceClass(
        name="c3.medium_dublin",
        price=TimeRatioValue(1.65, TimeUnit("h")),
        region=region_dublin,
    )

    m3_large_madrid = InstanceClass(
        name="m3.large_madrid",
        price=TimeRatioValue(3.4, TimeUnit("h")),
        region=region_madrid,
    )
    m3_large_dublin = InstanceClass(
        name="m3.large_dublin",
        price=TimeRatioValue(3.4, TimeUnit("h")),
        region=region_dublin,
    )

    ics = (
        ic_m5_xlarge_ireland,
        ic_m5_2xlarge_ireland,
        ic_m5_xlarge_hong_kong,
        ic_m5_2xlarge_hong_kong,
        c3_medium_madrid,
        c3_medium_dublin,
        m3_large_madrid,
        m3_large_dublin,
    )

    app_a0 = App(name="a0", max_resp_time=TimeValue(request.param, TimeUnit("s")))
    app_a1 = App(name="a1", max_resp_time=TimeValue(0.325, TimeUnit("s")))

    # The values are the performance (in hours) and the S_ia (in seconds).
    # This is a short cut for not having to repeat all units
    perf_dict = {
        (app_a0, ic_m5_xlarge_ireland): (2000, 0.1),
        (app_a0, ic_m5_2xlarge_ireland): (4000, 0.1),
        #
        (app_a0, ic_m5_xlarge_hong_kong): (2000, 0.1),
        (app_a0, ic_m5_2xlarge_hong_kong): (4000, 0.1),
        #
        (app_a0, c3_medium_madrid): (16000, 0.1),
        (app_a0, c3_medium_dublin): (16000, 0.1),
        #
        (app_a0, m3_large_madrid): (32000, 0.1),
        (app_a0, m3_large_dublin): (32000, 0.1),
        #
        (app_a1, ic_m5_xlarge_ireland): (9000, 0.12),
        (app_a1, ic_m5_2xlarge_ireland): (12000, 0.12),
        #
        (app_a1, ic_m5_xlarge_hong_kong): (9000, 0.12),
        (app_a1, ic_m5_2xlarge_hong_kong): (12000, 0.12),
        #
        (app_a1, c3_medium_madrid): (24000, 0.12),
        (app_a1, c3_medium_dublin): (24000, 0.12),
        #
        (app_a1, m3_large_madrid): (48000, 0.12),
        (app_a1, m3_large_dublin): (48000, 0.12),
    }

    perfs = {}
    for p, v in perf_dict.items():
        perfs[p] = Performance(
            value=TimeRatioValue(v[0], TimeUnit("h")),
            slo=TimeValue(v[1], TimeUnit("s")),
        )

    system = System(apps=(app_a0, app_a1), ics=ics, perfs=perfs, latencies=latencies)

    workloads = {
        # Edge regions
        (app_a0, region_dublin): Workload(
            values=(5000, 10000, 13123, 0, 16000, 15000),
            time_unit=TimeUnit("h"),
        ),
        (app_a0, region_madrid): Workload(
            values=(6000, 4000, 4000, 0, 15000, 0),
            time_unit=TimeUnit("h"),
        ),
        #
        (app_a1, region_dublin): Workload(
            values=(4000, 600, 600, 0, 10854, 0),
            time_unit=TimeUnit("h"),
        ),
        (app_a1, region_madrid): Workload(
            values=(3000, 900, 900, 0, 1002, 0),
            time_unit=TimeUnit("h"),
        ),
    }

    return system, workloads
