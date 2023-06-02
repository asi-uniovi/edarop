"""This module generates a solution with four regions (two edge, two cloud)."""

import pickle
from typing import Iterable

from cloudmodel.unified.units import (
    ComputationalUnits,
    CurrencyPerTime,
    RequestsPerTime,
    Time,
)
from edarop.model import (
    App,
    InstanceClass,
    Latency,
    Performance,
    Problem,
    Requests,
    Region,
    System,
    Workload,
)
from edarop.edarop import EdaropCAllocator


def int2req_tuple(int_list: Iterable[int]) -> tuple[Requests, ...]:
    """Converts an interable of ints to a tuple of Requests."""
    return tuple(Requests(f"{i} reqs") for i in int_list)


class Edarop2CloudRegions2EdgeRegions2Apps:
    """Two cloud regions and two edge regions and two apps. It is based on prices and
    performances from Amazon and Equinix."""

    def __init__(self) -> None:
        self.system = None
        self.workloads = None

    def __set_up(self) -> None:
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
            cores=ComputationalUnits("1 core"),
        )
        ic_m5_2xlarge_ireland = InstanceClass(
            name="m5.2xlarge_ireland",
            price=CurrencyPerTime("0.428 usd/h"),
            region=region_ireland,
            cores=ComputationalUnits("1 core"),
        )
        ic_m5_4xlarge_ireland = InstanceClass(
            name="m5.4xlarge_ireland",
            price=CurrencyPerTime("0.856 usd/h"),
            region=region_ireland,
            cores=ComputationalUnits("1 core"),
        )

        ic_m5_xlarge_hong_kong = InstanceClass(
            name="m5.xlarge_hong_kong",
            price=CurrencyPerTime("0.264 usd/h"),
            region=region_hong_kong,
            cores=ComputationalUnits("1 core"),
        )
        ic_m5_2xlarge_hong_kong = InstanceClass(
            name="m5.2xlarge_hong_kong",
            price=CurrencyPerTime("0.528 usd/h"),
            region=region_hong_kong,
            cores=ComputationalUnits("1 core"),
        )
        ic_m5_4xlarge_hong_kong = InstanceClass(
            name="m5.4xlarge_hong_kong",
            price=CurrencyPerTime("1.056 usd/h"),
            region=region_hong_kong,
            cores=ComputationalUnits("1 core"),
        )

        c3_medium_madrid = InstanceClass(
            name="c3.medium_madrid",
            price=CurrencyPerTime("1.65 usd/h"),
            region=region_madrid,
            cores=ComputationalUnits("1 core"),
        )
        c3_medium_dublin = InstanceClass(
            name="c3.medium_dublin",
            price=CurrencyPerTime("1.65 usd/h"),
            region=region_dublin,
            cores=ComputationalUnits("1 core"),
        )

        m3_large_madrid = InstanceClass(
            name="m3.large_madrid",
            price=CurrencyPerTime("3.4 usd/h"),
            region=region_madrid,
            cores=ComputationalUnits("1 core"),
        )
        m3_large_dublin = InstanceClass(
            name="m3.large_dublin",
            price=CurrencyPerTime("3.4 usd/h"),
            region=region_dublin,
            cores=ComputationalUnits("1 core"),
        )

        ics = [
            ic_m5_xlarge_ireland,
            ic_m5_2xlarge_ireland,
            ic_m5_4xlarge_ireland,
            ic_m5_xlarge_hong_kong,
            ic_m5_2xlarge_hong_kong,
            ic_m5_4xlarge_hong_kong,
            c3_medium_madrid,
            c3_medium_dublin,
            m3_large_madrid,
            m3_large_dublin,
        ]

        app_a0 = App(name="a0", max_resp_time=Time("0.2 s"))
        app_a1 = App(name="a1", max_resp_time=Time("0.325 s"))

        # The values are the performance (in req/hour) and the S_ia (in seconds).
        # This is a short cut for not having to repeat all units
        perf_dict = {
            (app_a0, ic_m5_xlarge_ireland): (2000, 0.1),
            (app_a0, ic_m5_2xlarge_ireland): (4000, 0.1),
            (app_a0, ic_m5_4xlarge_ireland): (8000, 0.1),
            #
            (app_a0, ic_m5_xlarge_hong_kong): (2000, 0.1),
            (app_a0, ic_m5_2xlarge_hong_kong): (4000, 0.1),
            (app_a0, ic_m5_4xlarge_hong_kong): (8000, 0.1),
            #
            (app_a0, c3_medium_madrid): (16000, 0.1),
            (app_a0, c3_medium_dublin): (16000, 0.1),
            #
            (app_a0, m3_large_madrid): (32000, 0.1),
            (app_a0, m3_large_dublin): (32000, 0.1),
            #
            (app_a1, ic_m5_xlarge_ireland): (3000, 0.12),
            (app_a1, ic_m5_2xlarge_ireland): (6000, 0.12),
            (app_a1, ic_m5_4xlarge_ireland): (12000, 0.12),
            #
            (app_a1, ic_m5_xlarge_hong_kong): (3000, 0.12),
            (app_a1, ic_m5_2xlarge_hong_kong): (6000, 0.12),
            (app_a1, ic_m5_4xlarge_hong_kong): (12000, 0.12),
            #
            (app_a1, c3_medium_madrid): (24000, 0.12),
            (app_a1, c3_medium_dublin): (24000, 0.12),
            #
            (app_a1, m3_large_madrid): (48000, 0.12),
            (app_a1, m3_large_dublin): (48000, 0.12),
        }

        perfs = {}
        for perf, value in perf_dict.items():
            perfs[perf] = Performance(
                value=RequestsPerTime(f"{value[0]} req/h"),
                slo=Time(f"{value[1]} s"),
            )

        self.system = System(
            apps=[app_a0, app_a1], ics=ics, perfs=perfs, latencies=latencies
        )

        self.workloads = {
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

    def dump_sol(self) -> None:
        """Test a system that is feasible with a cost optimization problem."""
        self.__set_up()
        problem = Problem(system=self.system, workloads=self.workloads)

        allocator = EdaropCAllocator(problem)
        sol = allocator.solve()

        # Save the solution to a pickle file
        with open("sols/sol_4_regs.p", "wb") as f:
            pickle.dump(sol, f)


def main():
    """Main function."""
    test = Edarop2CloudRegions2EdgeRegions2Apps()
    test.dump_sol()


if __name__ == "__main__":
    main()
