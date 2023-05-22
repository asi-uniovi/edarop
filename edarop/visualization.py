"""This module provides ways of visualizing problems and solutions for
edarop."""

from typing import Dict, List, Any, Tuple

from rich.console import Console
from rich.table import Table
from rich import print

from cloudmodel.unified.units import Currency, Time

from .model import (
    Solution,
    InstanceClass,
    App,
    Status,
    Region,
    COST_UNDEFINED,
    TIME_UNDEFINED,
)

from .analysis import SolutionAnalyzer


class SolutionPrettyPrinter:
    """Utilty methods to create pretty presentations of solutions."""

    def __init__(self, sol: Solution):
        self.sol = sol
        self.console = Console()

    def get_tables(self, detail_regions=True) -> List[Table]:
        """Returns a list of tables, one for each application."""
        if self.sol.solving_stats.status not in [
            Status.OPTIMAL,
            Status.INTEGER_FEASIBLE,
        ]:
            return []

        return [
            self.get_table_app(a, detail_regions) for a in self.sol.problem.system.apps
        ]

    def get_summary(self) -> str:
        """Returns a summary of the solution."""
        if self.sol.solving_stats.status not in [
            Status.OPTIMAL,
            Status.INTEGER_FEASIBLE,
        ]:
            return f"Non feasible solution. [bold red]{self.sol.solving_stats.status}"

        sol_analyzer = SolutionAnalyzer(self.sol)
        res = f"\nTotal cost: {sol_analyzer.cost()}"

        if self.sol.problem.max_cost != COST_UNDEFINED:
            res += f" (max. cost: {self.sol.problem.max_cost})"

        avg_resp_time = sol_analyzer.avg_resp_time().to("s").magnitude
        res += f"\nAverage response time: {avg_resp_time:.3f} s"

        if self.sol.problem.max_avg_resp_time != TIME_UNDEFINED:
            res += f" (max. avg. resp. time: {self.sol.problem.max_avg_resp_time})"

        deadline_miss_rate = sol_analyzer.deadline_miss_rate()
        res += f"\nDeadline miss ratio: {deadline_miss_rate:.3f}"

        return res

    def print(self, detail_regions=True):
        """Prints a table for each application and a summary of the solution."""
        tables = self.get_tables(detail_regions)
        for table in tables:
            print(table)

        print(self.get_summary())

    def get_table_app(self, app: App, detail_regions=True) -> Table:
        """Returns a Rich table with the solution for one a app."""
        table = self.__create_alloc_table(app, detail_regions)

        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]

            total_num_vms = 0
            total_cost = Currency("0 usd")
            total_num_reqs = 0
            total_resp_time = Time("0 s")
            first = True
            for index, num_vms in alloc.ics.items():
                alloc_app = index[0]

                # Print a row only if it is for this app and it uses at least
                # 1 VM
                if alloc_app != app or num_vms < 1:
                    continue

                ic = index[1]
                unit_price = ic.price * self.sol.problem.time_slot_unit
                cost = num_vms * unit_price

                total_num_vms += num_vms
                total_cost += cost

                if first:
                    time_slot = str(k)
                    first = False
                else:
                    time_slot = ""

                table.add_row(time_slot, ic.name, str(int(num_vms)), f"{cost:.3f}")

                if detail_regions:
                    rows = self.__compute_region_rows(time_slot=k, app=app, ic=ic)
                    for row in rows:
                        table.add_row(
                            "",
                            f"  {row['region_name']}",
                            "",
                            "",
                            f"{int(row['num_reqs']):_}",
                            f"{row['avg_resp_time']:.3f}",
                        )

                        total_num_reqs += int(row["num_reqs"])
                        total_resp_time += int(row["num_reqs"]) * row["avg_resp_time"]

            table.add_section()

            if total_num_reqs > 0:
                total_avg_resp_time = f"{total_resp_time/total_num_reqs:.5f}"
            else:
                total_avg_resp_time = ""

            table.add_row(
                "total",
                "",
                str(int(total_num_vms)),
                f"{total_cost:.2f}",
                f"{total_num_reqs:_}",
                total_avg_resp_time,
            )

            table.add_section()

        return table

    def print_table_app(self, app: App, detail_regions=True):
        """Prints a table with information about the allocation for an app."""
        table = self.get_table_app(app, detail_regions)
        self.console.print(table)

    @staticmethod
    def __create_alloc_table(app: App, detail_regions: bool):
        """Creates a table for the allocation with its headers."""
        table = Table(
            title=f"Application {app.name} - max. resp. time: {app.max_resp_time}"
        )
        table.add_column("t")
        table.add_column("ic / src" if detail_regions else "ic")
        table.add_column("num vms")
        table.add_column("total cost")

        if detail_regions:
            table.add_column("num reqs")
            table.add_column("avg resp_time (s)")

        return table

    def __compute_region_rows(
        self, time_slot: int, app: App, ic: InstanceClass
    ) -> List[Dict[str, Any]]:
        """Computes and returns a list of values that should be shown in each
        row for each region with the allocation for an app with an instance
        class."""
        rows = []
        for index, num_reqs in self.sol.alloc.time_slot_allocs[time_slot].reqs.items():
            alloc_app, region, alloc_ic = index
            if app != alloc_app or ic != alloc_ic or num_reqs == 0:
                continue

            try:
                avg_resp_time = self.sol.problem.system.resp_time(app, region, ic).to(
                    "s"
                )
            except KeyError:
                # This happens when there is no latency information between the
                # source region and the ic region
                avg_resp_time = float("NaN")
            rows.append(
                {
                    "region_name": region.name,
                    "num_reqs": num_reqs,
                    "avg_resp_time": avg_resp_time,
                }
            )

        return rows


class ProblemPrettyPrinter:
    """Utility functions to show pretty presentation of a problem."""

    def __init__(self, problem):
        self.problem = problem

    def print(self):
        """Prints information about the problem."""
        self.print_ics()
        self.print_apps()
        self.print_latencies()
        self.print_perfs()

    def table_ics(self):
        """Returns a table with information about the instance classes grouped
        by regions."""
        table = Table(title="Regions and instance classes")
        table.add_column("Region")
        table.add_column("Instance class")
        table.add_column("Price")

        for region in self.problem.regions:
            ics = [ic for ic in self.problem.system.ics if ic.region == region]

            first = True
            for ic in ics:
                if first:
                    region_name = region.name
                    first = False
                else:
                    region_name = ""

                table.add_row(region_name, ic.name, str(ic.price))

            table.add_section()

        return table

    def print_ics(self):
        """Prints information about the instance classes."""
        print(self.table_ics())

    def workload_for_app(self, app: App) -> Tuple[int, Dict[Region, int]]:
        """Returns a tuple with the total workload for an app in all regions and
        a dictionary with the workload for each region."""
        total_wl = 0
        wl_per_region = {}
        for region in self.problem.regions:
            if (app, region) in self.problem.workloads:
                wl_per_region[region] = sum(
                    self.problem.workloads[(app, region)].values
                )
                total_wl += wl_per_region[region]

        return total_wl, wl_per_region

    def workload_info(self) -> str:
        """Returns a string with information about the workload length"""
        workload_len = self.problem.workload_len
        a_workload = list(self.problem.workloads.values())[0]
        time_unit = a_workload.time_unit
        return f"{workload_len} time slots of {time_unit}"

    def table_apps(self):
        """Returns a rich table with information about the apps, including the
        maximum response time and the workload"""
        workload_info = self.workload_info()

        table = Table(title="Apps")
        table.add_column("Name")
        table.add_column("Max. resp. time.")
        table.add_column(f"Workload ({workload_info})")

        for app in self.problem.system.apps:
            total_wl, wl_per_region = self.workload_for_app(app)
            table.add_row(app.name, str(app.max_resp_time), f"total: {total_wl:_}")
            for reg, wl_reg in wl_per_region.items():
                table.add_row("", "", f"  {reg.name}: {wl_reg:_}")

            table.add_section()

        return table

    def print_apps(self):
        """Prints information about the apps."""
        print(self.table_apps())

    def table_latencies(self):
        """Returns a rich table with the latencies betweeb regions."""
        table = Table(title="Latencies (ms)")
        table.add_column("src / dst")
        for region in self.problem.regions:
            table.add_column(region.name)

        latency_rows = []
        for src in self.problem.regions:
            row = [src.name]
            for dst in self.problem.regions:
                if (src, dst) not in self.problem.system.latencies:
                    row.append("-")
                else:
                    latency = self.problem.system.latencies[(src, dst)]
                    latency_ms = latency.value.to("ms").magnitude
                    row.append(f"{latency_ms:.2f}")

            if not all(r == "-" for r in row[1:]):
                latency_rows.append(row)

        for latency in latency_rows:
            table.add_row(*latency)

        return table

    def print_latencies(self):
        """Prints information about the latencies."""
        print(self.table_latencies())

    def print_perfs(self):
        """Prints information about the performance."""
        table = Table(title="Performances")
        table.add_column("Instance class")
        table.add_column("App")
        table.add_column("RPS")
        table.add_column("Max. resp. time")
        table.add_column("Price per million req.")

        for ic in self.problem.system.ics:
            first = True
            for app in self.problem.system.apps:
                if (app, ic) not in self.problem.system.perfs:
                    continue  # Not all ICs handle all apps

                if first:
                    ic_column = f"{ic.name} - {ic.region.name}"
                    first = False
                else:
                    ic_column = ""

                perf = self.problem.system.perfs[(app, ic)]
                price_per_req = 1e6 * (
                    ic.price.to("usd/hour") / perf.value.to("req/hour")
                )
                table.add_row(
                    ic_column,
                    app.name,
                    str(perf.value.magnitude),
                    str(perf.slo),
                    f"{price_per_req:.2f}",
                )

            table.add_section()

        print(table)
