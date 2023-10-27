import asyncio
from datetime import datetime, timedelta


class TimeDelimitedCoroutine:
    """
    A class that invokes a coroutine if a minimum time has elapsed since the last invocation.

    Attributes:
        last_runtime (datetime): The timestamp of the last invocation.
        min_time (timedelta): The minimum time that needs to elapse before invoking the coroutine.
        routine (asyncio.coroutine): The coroutine to be invoked.

    """

    def __init__(self, min_time: timedelta, routine: asyncio.coroutines):
        """
        Initializes the TimedCoroutine instance.

        Args:
            min_time (timedelta): The minimum time that needs to elapse before invoking the coroutine.
            routine (asyncio.coroutine): The coroutine to be invoked.

        """
        self.last_runtime = datetime.now()
        self.min_time = min_time
        self.routine = routine

    async def invoke_if_time(self, **kwargs):
        """
        Invokes the coroutine if the minimum time has elapsed since the last invocation.

        Args:
            kwargs (dict): Keyword arguments to be passed to the coroutine.

        """
        if datetime.now() - self.last_runtime > self.min_time:
            await self.invoke(**kwargs)

    async def invoke(self, **kwargs):
        """
        Invokes the coroutine and updates the last_runtime attribute.

        Args:
            kwargs (dict): Keyword arguments to be passed to the coroutine.

        Returns:
            The result of the coroutine.

        """
        self.last_runtime = datetime.now()
        return await self.routine(**kwargs)
