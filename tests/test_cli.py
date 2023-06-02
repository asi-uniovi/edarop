"""Tests for the command line interface."""
import unittest

from click.testing import CliRunner

from edarop import cli


class TestCliModule(unittest.TestCase):
    """Test the command line interface"""

    def test_cli_print_prob(self):
        """Test the print-prob command."""

        runner = CliRunner()
        result = runner.invoke(
            cli.main,
            [
                "print-prob",
                "tests/sols/sol_4_regs.p",
            ],
        )

        assert result.exit_code == 0

    def test_cli_print_sol(self):
        """Test the print-sol command."""

        runner = CliRunner()
        result = runner.invoke(
            cli.main,
            [
                "print-sol",
                "tests/sols/sol_4_regs.p",
            ],
        )

        assert result.exit_code == 0
