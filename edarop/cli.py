"""Console script for edarop."""
import sys
import pickle
import click

from cloudmodel.unified.units import ureg
from pint import set_application_registry

from .visualization import ProblemPrettyPrinter, SolutionPrettyPrinter

set_application_registry(ureg)


@click.group()
def main():
    """Console script for edarop."""


@main.command()
@click.argument("file_name", type=click.Path(exists=True))
def print_prob(file_name):
    """Prints the problem in the FILE_NAME solution pickle file."""
    with open(file_name, "rb") as sol_file:
        sol = pickle.load(sol_file)
        ProblemPrettyPrinter(sol.problem).print()


@main.command()
@click.argument("file_name", type=click.Path(exists=True))
def print_sol(file_name):
    """Prints the solution in the FILE_NAME solution pickle file."""
    with open(file_name, "rb") as sol_file:
        sol = pickle.load(sol_file)
        SolutionPrettyPrinter(sol).print()


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
