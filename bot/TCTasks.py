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
    A special task object for running coroutines at specific timedelta intervals,
     managed within the TCTaskManager singleton.  This was made 

    Args:
        name (str): The unique name of the task.  Used to identify the task.
        time_interval (relativedelta_sp): An extension of dateutil.relativedelta for running the task,
            that can take in a list of weekdays within the weekday paramete.
            See dateutil.relativedelta for details.
        next_run (Datetime): next date and time to run the task.
        parent_db (Class): Reference to a parent Database that the name is stored within.
        run_number( integer or None): 
    Attributes:
        name (str): The name of the task.
        id (int): The unique ID of the task.
        time_interval (relativedelta): A relative time interval for running the task.
        last_run (datetime): The datetime of the last time the task was run.
        to_run_next (datetime): The datetime of the next time the task is scheduled to run.
        is_running (bool): A flag indicating whether the task is currently running.
        running_task (Task): The asyncio.Task object representing the running task, if any.
        funct (coroutine): A passed in coroutine to be passed into the wrapper function in assign_wrapper
        wrapper (coroutine): coroutine containing func that runs the class, and then determines the next time to run the task.
    """

    def __init__(self, name, time_interval, id=0, next_run=None, parent_db=None, run_number=None):
        self.name = name
        self.parent_db=parent_db
        self.id = id
        self.time_interval = time_interval
        self.last_run = None

        self.running_task = None
        self.is_running=False
        self.funct=None
        self.wrapper=None
        self.limited=False
        if run_number!=None:
            self.limited=True
        self.run_number=run_number

        self.to_run_next = next_run
        if self.to_run_next==None:
            self.to_run_next=datetime.now()
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
            print(f"{self.name} not ready. Next run in {time_until}")
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
                remove_check=False
                if self.limited:
                    self.run_number-=1
                    if self.run_number<=0:
                        print("To be removed.")
                        remove_check=True
                if self.parent_db:
                    s,t=self.name.split("_")
                    try:
                        self.parent_db.update(int(s),t,self.to_run_next)
                    except:
                        remove_check=True
                if remove_check:
                    TCTaskManager.add_tombstone(self.name)
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
        return self.assign_wrapper(func)

    def next_run(self):
        """
        Calculates the datetime of the next time the task should be run based on the current time, last_run, and time_interval.

        Returns:
            The datetime of the next time the task should be run.
        """
        to_run_next = datetime.now().replace(second=0, microsecond=0) + self.time_interval
        dc=0
        while to_run_next<datetime.now():
            dc+=1
            to_run_next=(datetime.now().replace(second=0, microsecond=0)+ relativedelta(weeks=dc))+self.time_interval
            print(datetime.now(),self.to_run_next)
        return to_run_next


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
        self.to_delete=[]
    @classmethod
    def does_task_exist(cls, name):
        """
        Check if a TCTask object with the specified name is in the list of tasks.
        Args:
            name (str): The name of the TCTask object to find in the list of tasks.

        Returns:
            True if a task is already there, False if no matching task was found.
        """
        manager = cls.get_instance()
        for task in manager.tasks:
            if task.name == name:
                return True
        return False    
    @classmethod
    def change_task_time(cls, name,datetime):
        """
        Check if a TCTask object with the specified name is in the list of tasks.
        Args:
            name (str): The name of the TCTask object to find in the list of tasks.

        Returns:
            True if a task is already there, False if no matching task was found.
        """
        manager = cls.get_instance()
        for task in manager.tasks:
            if task.name == name:
                task.to_run_next=datetime
                return True
        return False

    @classmethod
    def add_task(cls, task):
        """
        Adds a TCTask object to the manager's list of tasks.
        called automatically.
        Args:
            task (TCTask): The TCTask object to add to the list of tasks.

        """
        print(f"added task {task.name}")
        manager = cls.get_instance()
        manager.tasks.append(task)

    @classmethod
    def remove_task(cls, name):
        """
        Removes the TCTask object with the specified name from the manager's list of tasks.
        Args:
            name (str): The name of the TCTask object to remove from the list of tasks.

        Returns:
            True if a task was removed, False if no matching task was found.
        """
        manager = cls.get_instance()
        for task in manager.tasks:
            if task.name == name:
                print(f"removing task {task.name}")
                manager.tasks.remove(task)
                return True
        return False

    @classmethod
    def add_tombstone(cls, name):
        """
        Adds the name of the task to the manager's list of tasks to be removed.
        Args:
            name (str): The name of the task to be removed from the list of tasks.
        """
        manager = cls.get_instance()
        manager.to_delete.append(name)

    async def run_tasks():
        """
        Runs all of the TCTask objects that can be run at a specific time.
        """
        # Check each task to see if it's time to run
        manager = TCTaskManager.get_instance()

        for task in manager.tasks:
            if task.name in manager.to_delete and task.is_running==False:
                TCTaskManager.remove_task(task.name)
                    
                    
            if task.can_i_run():
                asyncio.create_task(task.wrapper())

        # Wait for 1 second before checking again
        await asyncio.sleep(1)

