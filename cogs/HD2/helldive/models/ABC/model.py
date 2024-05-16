from typing import *
# pylint: disable=no-name-in-module
from pydantic import BaseModel
from datetime import datetime

class BaseApiModel(BaseModel):
    '''Base extended model class'''
    retrieved_at: datetime = datetime.now()

    def __getitem__(self, attr):
        """
        Get a field in the same manner as a dictionary.
        """
        return getattr(self, attr)

    def get(self, attr, default=None):
        if not hasattr(self, attr):
            return default
        return getattr(self, attr)