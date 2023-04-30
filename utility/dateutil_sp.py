import asyncio
from datetime import datetime, timedelta
from dateutil.relativedelta import *
from dateutil.parser import parse
from dateutil.rrule import *
from dateutil import tz

from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU
from discord.ext import tasks
class relativedelta_sp(relativedelta):
    """A subclass of `relativedelta` that extends its `weekday` attribute to accept a list of weekdays."""
    def __init__(self, *args, **kwargs):
        self.kwargs=kwargs
        myw,mym= kwargs.pop("weekday", None),  kwargs.pop("months", None)
        super().__init__(*args, **kwargs)
        self._weekday =myw
        
        self._months =mym
    @property
    def months(self):
        """Return the next valid month based on if self._months is 'var' or not."""
        if self._months == 'var':
            # Check if everything else within the relativedelta expression has been reached in the current month
            now = datetime.now()
            print( now.day >= self.day, now.hour >= self.hour, now.minute > self.minute)
            print(now.month,self.month)
            if now.month != self.month and self.month!=None:
                print('return here')
                return +1
            if now.day >= self.day and now.hour >= self.hour and now.minute > self.minute:
                print("DAY FAILUTE.")
                return +1
            return 0
        else:
            return self._months
        
    @months.setter
    def months(self, value):
        if isinstance(value, str) and value == 'var':
            self._months = value
        else:
            self._months = int(value)
    @property
    def weekday(self):
        """Return the next valid weekday based on the provided list of weekdays."""
        return self._get_weekday(self._weekday)
    @weekday.setter
    def weekday(self, value):
        if isinstance(value, list):
            value = list(value)
        self._weekday = value
    def _get_weekday(self, wd):
        """Return the next valid weekday based on if self._weekday is a list or not."""
 
        if isinstance(wd, list):
            weekdays = [MO, TU, WE, TH, FR, SA, SU]
            weekday_mask = [1 if wed in wd else 0 for wed in weekdays]
            now = datetime.now(tz.tzlocal())
            next_weekday = (now.weekday()+1) % 7
            try:
                next_weekday = next(i for i, x in enumerate(weekday_mask[next_weekday:] + weekday_mask[:next_weekday]) if x)
            except StopIteration:
                pass
            else:
                return weekdays[next_weekday]
        return self._weekday


