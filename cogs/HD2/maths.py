"""Common math expressions used by the module."""

from .helldive import *


class maths:

    @staticmethod
    def dps_to_lph(dps, maxHealth: float = 1000000.0):
        """Damage per second to liberation per hour."""
        output = (dps * 60 * 60) / maxHealth
        return output * 100.0

    @staticmethod
    def lph_to_dps(dps, maxHealth: float = 1000000.0):
        """Damage per second to liberation per hour."""
        output = (dps * 60 * 60) / maxHealth
        return output * 100.0

    @staticmethod
    def dps_to_eps(dps: float, regenRate: float, impactMultiplier: float):
        eps = (dps + regenRate) / impactMultiplier
        return eps
