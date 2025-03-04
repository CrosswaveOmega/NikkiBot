"""This is a simple calculator that, rather than use eval to solve math problems due to security issues, evaluates string
expressions with it's own calculation code."""

from .c_util import *
from .calc import evaluate_expression, OutContainer


async def setup(bot):
    import gui

    gui.print(f"loading in child module {__name__}")


async def teardown(bot):
    import gui

    gui.print(f"unloading child module {__name__}")
