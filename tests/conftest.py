"""Pytest configuration file for the edarop package."""
from typing import Iterable, Tuple, Dict

import pytest

from cloudmodel.unified.units import (
    CurrencyPerTime,
    Requests,
    RequestsPerTime,
    Time,
)

from edarop.model import (
    InstanceClass,
    Region,
    Workload,
    App,
    Latency,
    Performance,
    System,
)


def int2req_tuple(int_list: Iterable[int]) -> Tuple[Requests, ...]:
    """Converts an interable of ints to a tuple of Requests."""
    return tuple(Requests(f"{i} reqs") for i in int_list)


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
            value=Time("0.05 s"),
        ),
        (region_dublin, region_hong_kong): Latency(
            value=Time("0.2 s"),
        ),
        (region_dublin, region_dublin): Latency(
            value=Time("0.04 s"),
        ),
        (region_madrid, region_ireland): Latency(
            value=Time("0.07 s"),
        ),
        (region_madrid, region_hong_kong): Latency(
            value=Time("0.21 s"),
        ),
        (region_madrid, region_madrid): Latency(
            value=Time("0.045 s"),
        ),
    }

    ic_m5_xlarge_ireland = InstanceClass(
        name="m5.xlarge_ireland",
        price=CurrencyPerTime("0.214 usd/h"),
        region=region_ireland,
    )
    ic_m5_2xlarge_ireland = InstanceClass(
        name="m5.2xlarge_ireland",
        price=CurrencyPerTime("0.428 usd/h"),
        region=region_ireland,
    )

    ic_m5_xlarge_hong_kong = InstanceClass(
        name="m5.xlarge_hong_kong",
        price=CurrencyPerTime("0.264 usd/h"),
        region=region_hong_kong,
    )
    ic_m5_2xlarge_hong_kong = InstanceClass(
        name="m5.2xlarge_hong_kong",
        price=CurrencyPerTime("0.528 usd/h"),
        region=region_hong_kong,
    )

    c3_medium_madrid = InstanceClass(
        name="c3.medium_madrid",
        price=CurrencyPerTime("1.65 usd/h"),
        region=region_madrid,
    )
    c3_medium_dublin = InstanceClass(
        name="c3.medium_dublin",
        price=CurrencyPerTime("1.65 usd/h"),
        region=region_dublin,
    )

    m3_large_madrid = InstanceClass(
        name="m3.large_madrid",
        price=CurrencyPerTime("3.4 usd/h"),
        region=region_madrid,
    )
    m3_large_dublin = InstanceClass(
        name="m3.large_dublin",
        price=CurrencyPerTime("3.4 usd/h"),
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

    app_a0 = App(name="a0", max_resp_time=Time(f"{request.param} s"))
    app_a1 = App(name="a1", max_resp_time=Time("0.325 s"))

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
            value=RequestsPerTime(f"{v[0]} reqs/h"),
            slo=Time(f"{v[1]} s"),
        )

    system = System(apps=(app_a0, app_a1), ics=ics, perfs=perfs, latencies=latencies)

    workloads = {
        # Edge regions
        (app_a0, region_dublin): Workload(
            values=int2req_tuple([5000, 10000, 13123, 0, 16000, 15000]),
            time_unit=Time("1 h"),
        ),
        (app_a0, region_madrid): Workload(
            values=int2req_tuple([6000, 4000, 4000, 0, 15000, 0]),
            time_unit=Time("1 h"),
        ),
        #
        (app_a1, region_dublin): Workload(
            values=int2req_tuple([4000, 600, 600, 0, 10854, 0]),
            time_unit=Time("1 h"),
        ),
        (app_a1, region_madrid): Workload(
            values=int2req_tuple([3000, 900, 900, 0, 1002, 0]),
            time_unit=Time("1 h"),
        ),
    }

    return system, workloads
