import asyncio
import json
from typing import Any, Dict, List, Optional, Union
import aiohttp
from datetime import datetime, timezone


class ApiCore(dict):
    """The base class for all api operations."""

    endpoint = None
    method = None

    def __init__(self):
        pass

    @classmethod
    def create(cls, **kwargs):
        instance = cls()
        for key, value in kwargs.items():
            setattr(instance, key, value)
        return instance

    def to_dict(self):
        serialized_dict = {}
        for key, value in self.__dict__.items():
            if key not in ["endpoint", "method", "use_model"]:
                if value is not None:
                    serialized_dict[key] = value
        return serialized_dict

    def slimdown(self, max_size: int):
        """to deal with an exceeded payload size"""
        pass
