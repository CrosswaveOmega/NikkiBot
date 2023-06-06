import asyncio
from datetime import datetime
from typing import Dict, Optional, Type
import gui
from dateutil.parser import parse
from dateutil.rrule import *
from dateutil import tz
from queue import PriorityQueue
import discord
from dateutil.rrule import rrule,rrulestr, WEEKLY, SU
class TCTask:
    """
    A special task object for running coroutines at specific timedelta intervals,
     managed within the TCTaskManager singleton.  This was made because I felt 
     discord.tasks did not provide the needed logic.

    Args:
        name (str): The unique name of the task. Used to identify the task.
        time_interval (rrule): A dateutil.rrule for determining the next time to run the task.
        id (int): The unique ID of the task.  deprecated.
        next_run (Datetime): Next date and time to run the task.
        parent_db (Type[object]): Reference to a parent Database that the name is stored within.
        run_number (int or None): The maximum number of times the task should run, or None if unlimited.

    Attributes:
        name (str): The name of the task.
        id (int): The unique ID of the task.
        time_interval (rrule): A relative time interval for running the task.
        last_run (datetime): The datetime of the last time the task was run.
        to_run_next (datetime): The datetime of the next time the task is scheduled to run.
        is_running (bool): A flag indicating whether the task is currently running.
        parent_db (Type[object]): Optional reference to a parent Database that the name is stored within.
        running_task (Task): The asyncio.Task object representing the running task, if any.
        funct (coroutine): A passed in coroutine to be passed into the wrapper function in assign_wrapper
        wrapper (coroutine): coroutine containing func that runs the class, and then determines the next time to run the task.
    """

    def __init__(
        self,
        name: str, time_interval: rrule, id: int = 0,
        next_run: Optional[datetime] = None,
        parent_db: Optional[Type[object]] = None,
        run_number: Optional[int] = None
    ):
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
        '''Check if the TCTask can be launched.'''
        if self.is_running: return False
        if datetime.now() >= self.to_run_next:
            # Update last_run time and run the function as a coroutine
            return True
        else:
            # Print the time until next run
            #time_until = self.to_run_next - datetime.now()
            #gui.gprint(f"{self.name} not ready. Next run in {time_until}")
            return False
    def get_total_seconds_until(self):
        if self.is_running: return 0
        return int((self.to_run_next-datetime.now()).total_seconds())
    def time_left(self):
        '''Check if the TCTask can be launched.'''
        if self.is_running: return f"{self.name} is running."
        time_until = self.to_run_next - datetime.now()
        ctr=self.next_run()
        formatted_datetime = self.to_run_next.strftime("%b-%d-%Y %H:%M")
        next_formatted_datetime=ctr.strftime("%b-%d-%Y %H:%M")
        return f"{self.name} will run next on {formatted_datetime}, in {time_until}.  If right now, then {next_formatted_datetime}"
    def time_left_short(self):
        '''Check if the TCTask can be launched.'''
        if self.is_running: return f"{self.name}: RUNNING\n"
        next = self.to_run_next - datetime.now()
        ctr=self.next_run()
        days= hours=mins=""
        if next.days>0:days=str(next.days)+"d,"
        if (next.seconds // 3600)>0:hours=str(int(next.seconds // 3600))+"h,"
        if ((next.seconds // 60) % 60)>0:mins=str(int((next.seconds // 60) % 60))+"m"
        formatted_delta = f"{days}{hours}{mins}"
        return f"{self.name}: {formatted_delta}\n"
    
    def assign_wrapper(self,func):
        '''create the asyncronous wrapper with the passed in func.  '''
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
            """
            # Check if it's time to run the function
            if datetime.now() >= self.to_run_next:
                # Update last_run time and run the function as a coroutine
                TCTaskManager.set_running(self.name)
                self.last_run = datetime.now()
                self.is_running=True
                self.running_task = asyncio.create_task(func(*args, **kwargs))

                await self.running_task
                self.to_run_next = self.next_run()
                remove_check=False
                if self.limited:
                    self.run_number-=1
                    if self.run_number<=0:
                        remove_check=True
                if self.parent_db:
                    try:
                        self.parent_db.parent_callback(self.name,self.to_run_next)
                    except Exception as e:
                        gui.gprint(e)
                        remove_check=True
                if remove_check:
                    TCTaskManager.add_tombstone(self.name)
                self.is_running=False
                TCTaskManager.set_standby(self.name)
            else:
                pass
                # Print the time until next run
                #time_until = self.to_run_next - datetime.now()
                #gui.gprint(f"{self.name} not ready. Next run in {time_until}")
        self.wrapper=wrapper
        return wrapper

    def __call__(self):
        """
        Decorator for wrapping a coroutine function with the TCTask scheduling logic.

        Args:
            func (coroutine function): The coroutine function to wrap.

        Returns:
            The wrapped coroutine function.
        """
        
        return self.wrapper()

    def next_run(self):
        """
        Calculates the datetime of the next time the task should be run based on the current time, last_run, and time_interval.

        Returns:
            The datetime of the next time the task should be run.
        """
        # Calculate the next future occurrence
        next_occurrence = self.time_interval.after(datetime.now().replace(second=0, microsecond=0))
        return next_occurrence


class TCTaskManager:
    """
    Manager class for every TCTask object.

    Attributes:
        tasks (dict): A dictionary of all TCTask objects managed by the manager.
        to_delete(list): a list of TCTask object to delete, since.
    """
    #TODO: SPEED IT UP.
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TCTaskManager()
        return cls._instance

    def __init__(self):
        self.tasks: Dict[str, TCTask] ={}
        self.to_delete=[]
        self.myqueue=PriorityQueue()
        

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
        if name in manager.tasks:
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
        if name in manager.tasks:
            manager.tasks[name].to_run_next=datetime
            return True
        return False
    
    @classmethod
    def change_task_interval(cls, name,new_rrule):
        """
        Check if a TCTask object with the specified name is in the list of tasks.
        Args:
            name (str): The name of the TCTask object to find in the list of tasks.

        Returns:
            True if a task is already there, False if no matching task was found.
        """
        manager = cls.get_instance()
        if name in manager.tasks:
            manager.tasks[name].time_interval=new_rrule
            manager.tasks[name].to_run_next=manager.tasks[name].next_run()
            return manager.tasks[name].to_run_next
        return False

    @classmethod
    def add_task(cls, task):
        """
        Adds a TCTask object to the manager's list of tasks.
        called automatically.
        Args:
            task (TCTask): The TCTask object to add to the list of tasks.

        """
        gui.gprint(f"added task {task.name}")
        manager = cls.get_instance()
        manager.tasks[task.name]=(task)

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
        if name in manager.tasks:
            gui.gprint(f"removing task {name}")
            manager.tasks.pop(name)
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

    @classmethod
    def set_running(cls, name):
        """
        Set task name into running mode, don't re add to the priority queue
        Args:
            name (str): The name of the task to be ran.
        """
        manager = cls.get_instance()
        gui.gprint(name, " is running")
        #manager.to_delete.append(name)

    @classmethod
    def set_standby(cls, name):
        """
        Set task name into standby mode, readd to priority queue
        Args:
            name (str): The name of the task to standby
        """
        manager = cls.get_instance()
        gui.gprint(name, " is standby")
        #manager.to_delete.append(name)

    @classmethod
    def task_check(cls):
        """
        Runs all of the TCTask objects that can be run at a specific time.
        """
        # Check each task to see if it's time to run
        manager = TCTaskManager.get_instance()
        task_string_list=[]
        for key, task in manager.tasks.items():
            task_string_list.append(task.time_left()+"\n")
        return task_string_list

    @classmethod
    def get_task_status(cls):
        '''get a small string that shows the current number of scheduled and running tasks.'''
        manager = TCTaskManager.get_instance()
        running=scheduled=0
        deltas=[]
        output=output2=""
        sorted_dict = sorted( manager.tasks.items(), key=lambda x: x[1].get_total_seconds_until())
        for key, task in sorted_dict:
            output2+=task.time_left_short()
            if task.is_running:
                running+=1
            else:
                scheduled+=1
                deltas.append(task.to_run_next - datetime.now())
                
        if running>0: output+=f"Running:{running}, "
        if scheduled>0: output+=f"Scheduled:{scheduled}, "
        if deltas:
            next=min(deltas, key=lambda x: x.total_seconds())
            days= hours=mins=""
            if next.days>0:days=str(next.days)+"d,"
            if (next.seconds // 3600)>0:hours=str(int(next.seconds // 3600))+"h,"
            if ((next.seconds // 60) % 60)>0:mins=str(int((next.seconds // 60) % 60))+"m"
            formatted_delta = f"next auto task in {days}{hours}{mins}"
            output+=formatted_delta
        return output, output2

    async def run_tasks():
        """
        Runs all of the TCTask objects that can be run at a specific time.
        """
        # Check each task to see if it's time to run
        manager = TCTaskManager.get_instance()
        for name in manager.to_delete:
            task=manager.tasks[name]
            if task.is_running==False:  TCTaskManager.remove_task(task.name)
        manager.to_delete=[]
        for key, task in manager.tasks.items():
            if task.can_i_run():
                asyncio.create_task(task())

        # Wait for 1 second before checking again
        await asyncio.sleep(1)

