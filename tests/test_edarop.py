#!/usr/bin/env python

"""Tests for `edarop` module."""
import pytest
from click.testing import CliRunner

from cloudmodel.unified.units import (
    ComputationalUnits,
    Currency,
    CurrencyPerTime,
    Requests,
    RequestsPerTime,
    Time,
)

from edarop import cli
from edarop.model import (
    InstanceClass,
    Status,
    Region,
    Workload,
    App,
    Latency,
    Performance,
    System,
    Problem,
)
from edarop.edarop import (
    EdaropCAllocator,
    EdaropRAllocator,
    EdaropCRAllocator,
    EdaropRCAllocator,
)
from edarop.visualization import SolutionPrettyPrinter, ProblemPrettyPrinter
from edarop.analysis import SolutionAnalyzer

from .conftest import int2req_tuple


def test_command_line_interface():
    """Test the CLI."""
    runner = CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0
    assert "edarop.cli.main" in result.output
    help_result = runner.invoke(cli.main, ["--help"])
    assert help_result.exit_code == 0
    assert "--help  Show this message and exit." in help_result.output


class TestEdaropBasic:
    """Basic tests with only one region, one instance class, one app."""

    def __set_up(self, slo_sec: float):
        region_ireland = Region("Ireland")
        instance = InstanceClass(
            name="m3.xlarge",
            price=CurrencyPerTime("0.1 usd/h"),
            region=region_ireland,
            cores=ComputationalUnits("1 core"),
        )
        app_a0 = App(name="a0", max_resp_time=Time("0.2 s"))
        latencies = {
            (region_ireland, region_ireland): Latency(
                Time("0.05 s"),
            )
        }
        perfs = {
            (app_a0, instance): Performance(
                value=RequestsPerTime("5 req/h"),
                slo=Time(f"{slo_sec} s"),
            )
        }
        self.system = System(
            apps=(app_a0,), ics=(instance,), perfs=perfs, latencies=latencies
        )

        self.workloads = {
            (app_a0, region_ireland): Workload(
                values=int2req_tuple([10, 20]),
                time_unit=Time("1 h"),
            )
        }

    def test_edarop_c_basic_feasible(self):
        """Test a simple cost optimization problem that is feasible."""
        self.__set_up(slo_sec=0.15)
        problem = Problem(system=self.system, workloads=self.workloads)
        allocator = EdaropCAllocator(problem)
        sol = allocator.solve()
        assert SolutionAnalyzer(sol).cost() == Currency("(0.2 + 0.4) usd")
        assert sol.solving_stats.status == Status.OPTIMAL
        assert SolutionAnalyzer(sol).deadline_miss_rate() == 0
        SolutionPrettyPrinter(sol).print(detail_regions=True)

    def test_edarop_c_basic_infeasible(self):
        """This is equal to the basic test, but it is infeasible because of the
        latency."""
        self.__set_up(slo_sec=0.15 * 1000)
        problem = Problem(system=self.system, workloads=self.workloads)
        allocator = EdaropCAllocator(problem)
        sol = allocator.solve()
        assert sol.solving_stats.status == Status.INFEASIBLE

    def test_edarop_r_basic_feasible(self):
        """Test a simple response time optimization problem that is feasible."""
        self.__set_up(slo_sec=0.15)
        problem = Problem(
            system=self.system, workloads=self.workloads, max_cost=Currency("0.6 usd")
        )
        allocator = EdaropRAllocator(problem)
        sol = allocator.solve()
        assert SolutionAnalyzer(sol).cost() == Currency("(0.2 + 0.4) usd")
        assert sol.solving_stats.status == Status.OPTIMAL
        SolutionPrettyPrinter(sol).print(detail_regions=True)

    def test_edarop_r_basic_infeasible_latency(self):
        """This is equal to the basic test, but it is infeasible because of the
        latency."""
        self.__set_up(slo_sec=0.15 * 1000)
        problem = Problem(
            system=self.system, workloads=self.workloads, max_cost=Currency("1e10 usd")
        )
        allocator = EdaropRAllocator(problem)
        sol = allocator.solve()
        assert sol.solving_stats.status == Status.INFEASIBLE

    def test_edarop_r_basic_infeasible_cost(self):
        """This is equal to the basic test, but it is infeasible because of the
        cost."""
        self.__set_up(slo_sec=0.15)
        problem = Problem(
            system=self.system, workloads=self.workloads, max_cost=Currency("0.5 usd")
        )
        allocator = EdaropRAllocator(problem)
        sol = allocator.solve()
        assert sol.solving_stats.status == Status.INFEASIBLE

    def test_edarop_r_cost_initialized(self):
        """This checks that an exception is raised is the cost is not
        initialized."""
        self.__set_up(slo_sec=0.15)
        problem = Problem(system=self.system, workloads=self.workloads)
        allocator = EdaropRAllocator(problem)
        with pytest.raises(ValueError):
            allocator.solve()

    def test_edarop_cr_basic_feasible(self):
        """This is equal to the basic edarop_c test but with edarop_cr."""
        self.__set_up(slo_sec=0.15)
        problem = Problem(system=self.system, workloads=self.workloads)
        allocator = EdaropCRAllocator(problem)
        sol = allocator.solve()
        assert SolutionAnalyzer(sol).cost() == Currency("(0.2 + 0.4) usd")
        assert sol.solving_stats.status == Status.OPTIMAL
        SolutionPrettyPrinter(sol).print(detail_regions=True)

    def test_edarop_rc_basic_feasible(self):
        """This is equal to the basic edarop_c test but with edarop_rc."""
        self.__set_up(slo_sec=0.15)
        problem = Problem(
            system=self.system, workloads=self.workloads, max_cost=Currency("10 usd")
        )
        allocator = EdaropRCAllocator(problem)
        sol = allocator.solve()
        assert SolutionAnalyzer(sol).cost() == Currency("(0.2 + 0.4) usd")
        assert sol.solving_stats.status == Status.OPTIMAL
        SolutionPrettyPrinter(sol).print(detail_regions=True)


class TestEdarop2CloudRegions2EdgeRegions2Apps:
    """Tests with only two cloud regions and two edge regions and two apps. It
    is based on prices and performances from Amazon and Equinix."""

    def __set_up(self):
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
        for p, v in perf_dict.items():
            perfs[p] = Performance(
                value=RequestsPerTime(f"{v[0]} req/h"),
                slo=Time(f"{v[1]} s"),
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

    def test_c_2CloudRegions2EdgeRegions2Apps_feasible(self):
        """Test a system that is feasible with a cost optimization problem."""
        self.__set_up()
        problem = Problem(system=self.system, workloads=self.workloads)
        ProblemPrettyPrinter(problem).print()

        allocator = EdaropCAllocator(problem)
        sol = allocator.solve()
        SolutionPrettyPrinter(sol).print(detail_regions=True)

        assert SolutionAnalyzer(sol).cost().to("usd").magnitude == pytest.approx(
            (
                (6 * 0.214 + 7 * 0.214 + (9 * 0.214) + 0 + 2 * 1.65 + 1.65)
                + (3 * 0.214 + 1 * 0.214 + 1 * 0.214 + 0 + 1 * 0.856 + 0)
            )
        )
        assert sol.solving_stats.status == Status.OPTIMAL
        SolutionPrettyPrinter(sol).print(detail_regions=True)

    def test_r_2CloudRegions2EdgeRegions2Apps_feasible(self):
        """Test a system that is feasible with a response time optimization
        problem."""
        self.__set_up()
        problem = Problem(
            system=self.system, workloads=self.workloads, max_cost=Currency("100 usd")
        )
        allocator = EdaropRAllocator(problem)
        sol = allocator.solve()
        SolutionPrettyPrinter(sol).print()

        avg_resp_time = SolutionAnalyzer(sol).avg_resp_time().to("s")
        assert avg_resp_time.magnitude == pytest.approx(0.1455567881140945)
        assert sol.solving_stats.status == Status.OPTIMAL

    def test_r_2CloudRegions2EdgeRegions2Apps_infeasible(self):
        """Test a system that is infeasible because of the cost with a response
        time optimization problem."""
        self.__set_up()
        problem = Problem(
            system=self.system, workloads=self.workloads, max_cost=Currency("10 usd")
        )
        allocator = EdaropRAllocator(problem)
        sol = allocator.solve()

        assert sol.solving_stats.status == Status.INFEASIBLE

    def test_cr_2CloudRegions2EdgeRegions2Apps_feasible(self):
        """Test a system that is feasible with a multi-objective optimization
        problem, first cost and then response time."""
        self.__set_up()
        problem = Problem(system=self.system, workloads=self.workloads)
        allocator = EdaropCRAllocator(problem)
        sol = allocator.solve()
        SolutionPrettyPrinter(sol).print(detail_regions=True)

        assert SolutionAnalyzer(sol).cost().to("usd").magnitude == pytest.approx(
            (
                (6 * 0.214 + 7 * 0.214 + (9 * 0.214) + 0 + 2 * 1.65 + 1.65)
                + (3 * 0.214 + 1 * 0.214 + 1 * 0.214 + 0 + 1 * 0.856 + 0)
            )
        )
        assert sol.solving_stats.status == Status.OPTIMAL

    def test_rc_2CloudRegions2EdgeRegions2Apps_feasible(self):
        """Test a system that is feasible with a multi-objective optimization
        problem, first response time and then cost."""
        self.__set_up()
        problem = Problem(
            system=self.system, workloads=self.workloads, max_cost=Currency("100 usd")
        )
        allocator = EdaropRCAllocator(problem)
        sol = allocator.solve()
        ProblemPrettyPrinter(problem).print()
        SolutionPrettyPrinter(sol).print(detail_regions=True)

        assert SolutionAnalyzer(sol).cost().to("usd").magnitude == pytest.approx(
            (
                (2 * 1.65 + 2 * 1.65 + 2 * 1.65 + 0 + 2 * 1.65 + 1 * 1.65)
                + (2 * 1.65 + 2 * 1.65 + 2 * 1.65 + 0 + 2 * 1.65 + 0)
            )
        )
        assert SolutionAnalyzer(sol).avg_resp_time() == Time("0.1455567881140945 s")
        assert sol.solving_stats.status == Status.OPTIMAL
        SolutionPrettyPrinter(sol).print(detail_regions=True)


class TestOneCloudRegionTwoEdge:
    """Tests with only one cloud region and two edge regions and one app. It is
    based on prices and performances from Amazon and Equinix."""

    def __set_up(self):
        # Cloud regions
        region_ireland = Region("Ireland")

        # Edge regions
        region_dublin = Region("Dublin")
        region_madrid = Region("Madrid")

        latencies = {
            (region_dublin, region_ireland): Latency(
                value=Time("0.05 s"),
            ),
            (region_dublin, region_dublin): Latency(
                value=Time("0.04 s"),
            ),
            (region_madrid, region_ireland): Latency(
                value=Time("0.07 s"),
            ),
        }

        ic_m5_xlarge_ireland = InstanceClass(
            name="m5.xlarge_ireland",
            price=CurrencyPerTime("0.214 usd/h"),
            region=region_ireland,
            cores=ComputationalUnits("1 core"),
        )
        ic_m5_4xlarge_ireland = InstanceClass(
            name="m5.4xlarge_ireland",
            price=CurrencyPerTime("0.856 usd/h"),
            region=region_ireland,
            cores=ComputationalUnits("1 core"),
        )

        c3_medium_dublin = InstanceClass(
            name="c3.medium_dublin",
            price=CurrencyPerTime("1.65 usd/h"),
            region=region_dublin,
            cores=ComputationalUnits("1 core"),
        )

        ics = [
            ic_m5_xlarge_ireland,
            ic_m5_4xlarge_ireland,
            c3_medium_dublin,
        ]

        app_a0 = App(name="a0", max_resp_time=Time("0.2 s"))

        # The values are the performance (in hours) and the S_ia (in seconds).
        # This is a short cut for not having to repeat all units
        perf_dict = {
            (app_a0, ic_m5_xlarge_ireland): (2000, 0.1),
            (app_a0, ic_m5_4xlarge_ireland): (8000, 0.1),
            #
            (app_a0, c3_medium_dublin): (16000, 0.1),
        }

        perfs = {}
        for p, v in perf_dict.items():
            perfs[p] = Performance(
                value=RequestsPerTime(f"{v[0]} req/h"),
                slo=Time(f"{v[1]} s"),
            )

        self.system = System(apps=[app_a0], ics=ics, perfs=perfs, latencies=latencies)

        self.workloads = {
            # Edge regions
            (app_a0, region_dublin): Workload(
                values=[Requests("13123 req")],
                time_unit=Time("1 h"),
            ),
            (app_a0, region_madrid): Workload(
                values=[Requests("4000 req")],
                time_unit=Time("1 h"),
            ),
        }

    def test_1cloud2edge1app(self):
        """Test a system that is feasible."""
        self.__set_up()
        problem = Problem(system=self.system, workloads=self.workloads)
        allocator = EdaropCAllocator(problem)
        sol = allocator.solve()
        SolutionPrettyPrinter(sol).print(detail_regions=True)

        assert SolutionAnalyzer(sol).cost().to("usd").magnitude == pytest.approx(
            9 * 0.214
        )
        assert sol.solving_stats.status == Status.OPTIMAL


class TestEdaropSameCost:
    """In this test, there is only one instance class and one app, but there are
    two regions with the same cost. The solution should be valid in any region,
    but in a multi-objective optimization, the region with less latency should
    be preferred."""

    def __set_up(self, slo_sec: float):
        region_ireland = Region("Ireland")  # Cloud
        region_dublin = Region("Dublin")  # Edge

        ic_ireland = InstanceClass(
            name="m3.xlarge_ireland",
            price=CurrencyPerTime("0.1 usd/h"),
            region=region_ireland,
            cores=ComputationalUnits("1 core"),
        )
        ic_dublin = InstanceClass(
            name="m3.xlarge_dublin",
            price=CurrencyPerTime("0.1 usd/h"),
            region=region_dublin,
            cores=ComputationalUnits("1 core"),
        )

        app_a0 = App(name="a0", max_resp_time=Time("0.2 s"))
        latencies = {
            (region_dublin, region_ireland): Latency(Time("0.05 s")),
            (region_dublin, region_dublin): Latency(Time("0.03 s")),
        }
        perfs = {
            (app_a0, ic_ireland): Performance(
                value=RequestsPerTime("5 req/h"),
                slo=Time(f"{slo_sec} s"),
            ),
            (app_a0, ic_dublin): Performance(
                value=RequestsPerTime("5 req/h"),
                slo=Time(f"{slo_sec} s"),
            ),
        }
        self.system = System(
            apps=(app_a0,),
            ics=(ic_ireland, ic_dublin),
            perfs=perfs,
            latencies=latencies,
        )

        self.workloads = {
            (app_a0, region_dublin): Workload(
                values=int2req_tuple([10, 20]),
                time_unit=Time("1 h"),
            ),
            (app_a0, region_ireland): Workload(
                values=int2req_tuple([0, 0]),
                time_unit=Time("1 h"),
            ),
        }

    def test_edarop_c_basic_same_cost_feasible(self):
        """Test a simple system that is feasible with edarop-c."""
        self.__set_up(slo_sec=0.15)
        problem = Problem(system=self.system, workloads=self.workloads)
        allocator = EdaropCAllocator(problem)
        sol = allocator.solve()

        assert SolutionAnalyzer(sol).cost() == Currency("(0.2 + 0.4) usd")
        assert sol.solving_stats.status == Status.OPTIMAL

        SolutionPrettyPrinter(sol).print(detail_regions=True)

    def test_edarop_cr_basic_same_cost_feasible(self):
        """Test a simple system that is feasible with edarop-cr."""
        self.__set_up(slo_sec=0.15)
        problem = Problem(system=self.system, workloads=self.workloads)
        allocator = EdaropCRAllocator(problem)
        sol = allocator.solve()
        sol_analyzer = SolutionAnalyzer(sol)

        assert sol_analyzer.cost() == Currency("(0.2 + 0.4) usd")
        assert sol_analyzer.avg_resp_time() == Time("0.18 s")
        assert sol.solving_stats.status == Status.OPTIMAL

        SolutionPrettyPrinter(sol).print(detail_regions=True)
