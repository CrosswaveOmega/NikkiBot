import asyncio
from datetime import datetime, timedelta
from dateutil.relativedelta import *
from dateutil.parser import parse
from dateutil.rrule import *
from dateutil import tz

from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU
from discord.ext import tasks
from utility import relativedelta_sp

class TCTask:
    """
    A task object for running coroutines at specific intervals.

    Args:
        name (str): The name of the task.
        time_interval (relativedelta_sp): An extension of dateutil.relativedelta for running the task,
            that can take in a list of weekdays within the weekday paramete.
            See dateutil.relativedelta for details.

    Attributes:
        name (str): The name of the task.
        id (int): The unique ID of the task.
        time_interval (relativedelta): A relative time interval for running the task.
        last_run (datetime): The datetime of the last time the task was run.
        to_run_next (datetime): The datetime of the next time the task is scheduled to run.
        is_running (bool): A flag indicating whether the task is currently running.
        running_task (Task): The asyncio.Task object representing the running task, if any.
    """

    def __init__(self, name, time_interval, id=0, next_run=datetime.now()):
        self.name = name
        self.id = id(self)
        self.time_interval = time_interval
        self.last_run = None
        self.to_run_next = next_run
        self.running_task = None
        self.is_running=False
        self.funct=None
        self.wrapper=None
        self.to_run_next=self.next_run()
        # Add self to the TCTaskManager upon initialization
        TCTaskManager.add_task(self)
    def can_i_run(self):
        if self.is_running: return False
        if datetime.now() >= self.to_run_next:
            # Update last_run time and run the function as a coroutine
            return True
        else:
            # Print the time until next run
            time_until = self.to_run_next - datetime.now()
            #print(f"{self.name} not ready. Next run in {time_until}")
            return False
    def assign_wrapper(self,func):
        self.funct = func  # Add the coroutine function to the TCTask object
        async def wrapper(*args, **kwargs):
            """
            The wrapped coroutine function.

            If it is time to run the task, the function is run as a coroutine,
            and the next to_run_time is launched.

            If it is not yet time to run the task, a message is printed indicating how long until the next run.

            Args:
                *args: Positional arguments to pass to the coroutine function.
                **kwargs: Keyword arguments to pass to the coroutine function.

            Returns:
                None.
            """
            # Check if it's time to run the function
            if datetime.now() >= self.to_run_next:
                # Update last_run time and run the function as a coroutine
                self.last_run = datetime.now()
                self.is_running=True
                self.running_task = asyncio.create_task(func(*args, **kwargs))

                await self.running_task
                self.to_run_next = self.next_run()
                self.is_running=False
            else:
                # Print the time until next run
                time_until = self.to_run_next - datetime.now()
                print(f"{self.name} not ready. Next run in {time_until}")
        self.wrapper=wrapper
        return wrapper
    def __call__(self, func):
        """
        Decorator for wrapping a coroutine function with the TCTask scheduling logic.

        Args:
            func (coroutine function): The coroutine function to wrap.

        Returns:
            The wrapped coroutine function.
        """
        self.funct = func  # Add the coroutine function to the TCTask object
        async def wrapper(*args, **kwargs):
            """
            The wrapped coroutine function.

            If it is time to run the task, the function is run as a coroutine,
            and the next to_run_time is launched.

            If it is not yet time to run the task, a message is printed indicating how long until the next run.

            Args:
                *args: Positional arguments to pass to the coroutine function.
                **kwargs: Keyword arguments to pass to the coroutine function.

            Returns:
                None.
            """
            # Check if it's time to run the function
            if datetime.now() >= self.to_run_next:
                # Update last_run time and run the function as a coroutine
                self.last_run = datetime.now()
                self.is_running=True
                self.running_task = asyncio.create_task(func(*args, **kwargs))

                await self.running_task
                self.to_run_next = self.next_run()
                self.is_running=False
            else:
                # Print the time until next run
                time_until = self.to_run_next - datetime.now()
                print(f"{self.name} not ready. Next run in {time_until}")
        self.wrapper=wrapper
        return wrapper

    def next_run(self):
        """
        Calculates the datetime of the next time the task should be run based on the current time, last_run, and time_interval.

        Returns:
            The datetime of the next time the task should be run.
        """
        self.to_run_next = datetime.now().replace(second=0, microsecond=0) + self.time_interval
        print(self.to_run_next)
        return self.to_run_next




class TCTaskManager:
    """
    A singleton class that manages TCTask objects.

    Attributes:
        tasks (list): A list of all TCTask objects managed by the manager.
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TCTaskManager()
        return cls._instance

    def __init__(self):
        self.tasks = []

    @classmethod
    def add_task(cls, task):
        """
        Adds a TCTask object to the manager's list of tasks.
        called automatically.
        Args:
            task (TCTask): The TCTask object to add to the list of tasks.

        """
        print("added task")
        manager = cls.get_instance()
        manager.tasks.append(task)

    async def run_tasks():
        """
        Runs all of the TCTask objects at once.
        """
        # Check each task to see if it's time to run
        manager = TCTaskManager.get_instance()
        for task in manager.tasks:
            if task.can_i_run():
                asyncio.create_task(task.wrapper())

        # Wait for 1 second before checking again
        await asyncio.sleep(1)

