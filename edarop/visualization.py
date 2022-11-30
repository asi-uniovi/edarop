"""This module provides ways of visualizing problems and solutions for
edarop."""

from rich.console import Console
from rich.table import Table

from .model import TimeUnit, Solution, InstanceClass, App, Status

from .analysis import SolutionAnalyzer


class SolutionPrettyPrinter:
    def __init__(self, sol: Solution):
        self.sol = sol
        self.console = Console()

    def print(self, detail_regions=True):
        if self.sol.status != Status.OPTIMAL:
            self.console.print(f"Not optimal solution. [bold red]{self.sol.status}")
            return

        for a in self.sol.problem.system.apps:
            self.print_table_app(a, detail_regions)

        sol_analyzer = SolutionAnalyzer(self.sol)
        print(f"\nTotal cost: {sol_analyzer.cost()}")
        avg_resp_time = sol_analyzer.avg_resp_time().to(TimeUnit("s"))
        print(f"Average response time: {avg_resp_time:.3f} s")

    def print_table_app(self, app: App, detail_regions=True):
        """Prints a table with information about the allocation for an app."""
        table = self.__create_table(app, detail_regions)

        for k in range(self.sol.problem.workload_len):
            alloc = self.sol.alloc.time_slot_allocs[k]

            first = True
            for index, num_vms in alloc.ics.items():
                alloc_app = index[0]
                if alloc_app != app or num_vms == 0:
                    continue

                ic = index[1]
                unit_price = ic.price.to(self.sol.problem.time_slot_unit)
                cost = num_vms * unit_price

                if first:
                    time_slot = str(k)
                    first = False
                else:
                    time_slot = ""

                table.add_row(time_slot, ic.name, str(int(num_vms)), f"{cost:.2f}")

                if detail_regions:
                    self.__add_rows_regions(table=table, time_slot=k, app=app, ic=ic)

            table.add_section()

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

    def __add_rows_regions(
        self, table: Table, time_slot: int, app: App, ic: InstanceClass
    ):
        """Adds a row for each region with the allocation for an app with an
        instance class"""
        for index, num_reqs in self.sol.alloc.time_slot_allocs[time_slot].reqs.items():
            alloc_app, region, alloc_ic = index
            if app != alloc_app or ic != alloc_ic or num_reqs == 0:
                continue

            avg_tresp = self.sol.problem.system.tresp(app, region, ic).to(TimeUnit("s"))
            table.add_row(
                "",
                f"  {region.name}",
                "",
                "",
                str(int(num_reqs)),
                f"{avg_tresp:.3f}",
            )
