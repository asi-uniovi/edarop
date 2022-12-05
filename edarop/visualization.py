"""This module provides ways of visualizing problems and solutions for
edarop."""

from typing import Any

from rich.console import Console
from rich.table import Table
from rich import print

from .model import TimeUnit, Solution, InstanceClass, App, Status

from .analysis import SolutionAnalyzer


class SolutionPrettyPrinter:
    def __init__(self, sol: Solution):
        self.sol = sol
        self.console = Console()

    def get_tables(self, detail_regions=True) -> list[Table]:
        if self.sol.status != Status.OPTIMAL:
            return []

        return [
            self.get_table_app(a, detail_regions) for a in self.sol.problem.system.apps
        ]

    def get_summary(self) -> str:
        if self.sol.status != Status.OPTIMAL:
            return f"Not optimal solution. [bold red]{self.sol.status}"

        sol_analyzer = SolutionAnalyzer(self.sol)
        res = f"\nTotal cost: {sol_analyzer.cost()}"

        avg_resp_time = sol_analyzer.avg_resp_time().to(TimeUnit("s"))
        res += f"\nAverage response time: {avg_resp_time:.3f} s"

        return res

    def print(self, detail_regions=True):
        tables = self.get_tables(detail_regions)
        for table in tables:
            print(table)

        print(self.get_summary())

    def get_table_app(self, app: App, detail_regions=True) -> Table:
        table = self.__create_table(app, detail_regions)

        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]

            total_num_vms = 0
            total_cost = 0.0
            total_num_reqs = 0
            first = True
            for index, num_vms in alloc.ics.items():
                alloc_app = index[0]
                if alloc_app != app or num_vms == 0:
                    continue

                ic = index[1]
                unit_price = ic.price.to(self.sol.problem.time_slot_unit)
                cost = num_vms * unit_price

                total_num_vms += num_vms
                total_cost += cost

                if first:
                    time_slot = str(k)
                    first = False
                else:
                    time_slot = ""

                table.add_row(time_slot, ic.name, str(int(num_vms)), f"{cost:.2f}")

                if detail_regions:
                    rows = self.__compute_region_rows(time_slot=k, app=app, ic=ic)
                    for row in rows:
                        table.add_row(
                            "",
                            f"  {row['region_name']}",
                            "",
                            "",
                            str(int(row["num_reqs"])),
                            f"{row['avg_tresp']:.3f}",
                        )

                        total_num_reqs += int(row["num_reqs"])

            table.add_section()

            table.add_row(
                "total",
                "",
                str(int(total_num_vms)),
                f"{total_cost:.2f}",
                str(total_num_reqs),
            )

            table.add_section()

        return table

    def print_table_app(self, app: App, detail_regions=True):
        """Prints a table with information about the allocation for an app."""
        table = self.get_table_app(app, detail_regions)
        self.console.print(table)

    @staticmethod
    def __create_table(app: App, detail_regions: bool):
        """Creates a table for the alloction with its headers."""
        table = Table(title=f"Application {app.name}")
        table.add_column("t")
        table.add_column("ic / src" if detail_regions else "ic")
        table.add_column("num vms")
        table.add_column("total cost")

        if detail_regions:
            table.add_column("num reqs")
            table.add_column("avg tresp (s)")

        return table

    def __compute_region_rows(
        self, time_slot: int, app: App, ic: InstanceClass
    ) -> list[dict[str, Any]]:
        """Computes and returns a list of values that should be shown in each
        row for each region with the allocation for an app with an instance
        class."""
        rows = []
        for index, num_reqs in self.sol.alloc.time_slot_allocs[time_slot].reqs.items():
            alloc_app, region, alloc_ic = index
            if app != alloc_app or ic != alloc_ic or num_reqs == 0:
                continue

            avg_tresp = self.sol.problem.system.tresp(app, region, ic).to(TimeUnit("s"))
            rows.append(
                {
                    "region_name": region.name,
                    "num_reqs": num_reqs,
                    "avg_tresp": avg_tresp,
                }
            )

        return rows
