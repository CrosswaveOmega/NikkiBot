import asyncio
from datetime import datetime as dt
from typing import Any, Callable, Coroutine, Dict, Optional, Type, Literal, TypeVar
import gui

from dateutil.rrule import rrule
import heapq
from queue import PriorityQueue
import logging

_coro = Callable[..., Coroutine[Any, Any, Any]]
CoroutineWrap = TypeVar("CoroutineWrap", bound=_coro)
Statuses = Literal["created", "standby", "running"]


logs = logging.getLogger("TCLogger")


class AutoRebalancePriorityQueue(PriorityQueue):
    """This is a special PriorityQueque that rebalances itself on new items."""

    def rebalance(self):
        with self.mutex:
            heapq.heapify(self.queue)


class TCTaskRef:
    """A separate identifier class that stores a reference to each task name."""

    __slots__ = ["name"]

    def __init__(self, name):
        self.name = name

    def get_task(self) -> "TCTask":
        return TCTaskManager.get_task(self.name)

    def __lt__(self, other):
        me = self.get_task()
        if me != None and other.get_task() is not None:
            return self.get_task().to_run_next < other.get_task().to_run_next
        return True


logs = logging.getLogger("TCLogger")


class TCTask:
    """
    A special task object for running coroutines at specific timedelta intervals,
        managed within the TCTaskManager singleton. This was made because I felt
     discord.tasks did not provide sufficient scheduling logic.

    Args:
        name (str): The unique name of the task. Used to identify the task.
        time_interval (rrule): A dateutil.rrule for determining the next time to run the task.
        next_run (Optional[dt]): Next date and time to run the task. Defaults to None.
        parent_db (Optional[Type[object]]): Reference to any Class with a parent_callback method,
        invoked after this class is done running.
          Defaults to None.
        run_number (Optional[int]): The maximum number of times the task should run, or None if unlimited. Defaults to None.

    Attributes:
        name (str): The unique name of the task.
        time_interval (rrule): A relative time interval for running the task.
        last_run (Optional[dt]): The dt of the last time the task was run.
        to_run_next (dt): The dt of the next time the task is scheduled to run.
        is_running (bool): A flag indicating whether the task is currently running.
        parent_db (Optional[Type[object]]): Reference to a parent Database that the name is stored within.
        running_task (Optional[asyncio.Task]): The asyncio.Task object representing the running task, if any.
        funct (Optional[coroutine]): A passed in coroutine to be passed into the wrapper function in assign_wrapper.
        wrapper (Optional[coroutine]): coroutine containing func that runs the class, and then determines the next time to run the task.
        limited (bool): A flag indicating whether the task runs are limited.
        run_number (Optional[int]): The maximum number of times the task should run, or None if unlimited.
    """

    __slots__ = [
        "name",
        "parent_db",
        "time_interval",
        "last_run",
        "status",
        "running_task",
        "is_running",
        "funct",
        "wrapper",
        "limited",
        "run_number",
        "to_run_next",
    ]

    def __init__(
        self,
        name: str,
        time_interval: rrule,
        next_run: Optional[dt] = None,
        parent_db: Optional[Type[object]] = None,
        run_number: Optional[int] = None,
    ):
        self.name: str = name
        self.parent_db: Optional[Type[object]] = parent_db
        self.time_interval: rrule = time_interval
        self.last_run: Optional[dt] = None
        self.status: Statuses = "created"
        self.running_task: Optional[asyncio.Task] = None
        self.is_running: bool = False
        self.funct: Optional[Coroutine] = None
        self.wrapper: Optional[Coroutine] = None
        self.limited: bool = False
        self.run_number: Optional[int] = run_number

        if run_number is not None:
            self.limited = True

        self.to_run_next: Optional[dt] = next_run
        if self.to_run_next is None:
            self.to_run_next = dt.now()
            self.to_run_next = self.next_run()
        # Add self to the TCTaskManager upon initialization
        TCTaskManager.add_task(self)

    def get_ref(self) -> TCTaskRef:
        """Return the TCTaskRef for this object."""
        return TCTaskRef(self.name)

    def can_i_run(self) -> bool:
        """Check if the TCTask can be launched."""
        if self.is_running:
            return False
        if dt.now() >= self.to_run_next:
            return True
        else:
            return False

    def get_total_seconds_until(self) -> int:
        """return the total number of seconds until the next run."""
        if self.is_running:
            return 0
        return int((self.to_run_next - dt.now()).total_seconds())

    def time_left(self) -> str:
        """Return a string indicating the next run time of this task."""
        if self.is_running:
            return f"{self.name} is running."
        time_until = self.to_run_next - dt.now()
        ctr = self.next_run()
        formatted_datetime = self.to_run_next.strftime("%b-%d-%Y %H:%M")
        next_formatted_datetime = ctr.strftime("%b-%d-%Y %H:%M")
        return f"{self.name} will run next on {formatted_datetime}, in {time_until}.  If right now, then {next_formatted_datetime}"

    def time_left_short(self) -> str:
        """Return a string indicating the next run time of this task."""
        if self.is_running:
            return f"{self.name}: RUNNING\n"
        nextt = self.to_run_next - dt.now()
        # ctr = self.next_run()
        days = hours = mins = ""
        if nextt.days > 0:
            days = str(nextt.days) + "d,"
        if (nextt.seconds // 3600) > 0:
            hours = str(int(nextt.seconds // 3600)) + "h,"
        if ((nextt.seconds // 60) % 60) > 0:
            mins = str(int((nextt.seconds // 60) % 60)) + "m"
        formatted_delta = f"{days}{hours}{mins},{nextt.seconds % 60}s"
        return f"{self.name}: {formatted_delta}\n"

    def time_left_shorter(self) -> str:
        """Return a string indicating the next run time of this task."""
        if self.is_running:
            return "RUNNING\n"
        nextt = self.to_run_next - dt.now()
        # ctr = self.next_run()
        days = hours = mins = ""
        if nextt.days > 0:
            days = str(nextt.days) + "d,"
        if (nextt.seconds // 3600) > 0:
            hours = str(int(nextt.seconds // 3600)) + "h,"
        if ((nextt.seconds // 60) % 60) > 0:
            mins = str(int((nextt.seconds // 60) % 60)) + "m"
        formatted_delta = f"{days}{hours}{mins},{nextt.seconds % 60}s"
        return f"{formatted_delta}\n"

    def assign_wrapper(self, func: CoroutineWrap) -> CoroutineWrap:
        """create the asyncronous wrapper with the passed in func."""
        self.funct = func  # Add the coroutine function to the TCTask object

        async def wrapper(*args: Any, **kwargs: Dict[str, Any]) -> None:
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
            if dt.now() >= self.to_run_next:
                # Update last_run time and run the function as a coroutine

                TCTaskManager.set_running(self.name)
                self.last_run = dt.now()
                self.is_running = True
                self.running_task = asyncio.create_task(func(*args, **kwargs))

                await self.running_task
                self.to_run_next = self.next_run()
                remove_check = False
                if self.limited:
                    # Subtract run number if limited.
                    self.run_number -= 1
                    if self.run_number <= 0:
                        remove_check = True
                if self.parent_db:
                    try:
                        self.parent_db.parent_callback(self.name, self.to_run_next)
                    except Exception as e:
                        logs.error(
                            "Something went wrong with the parent callback for task %s",
                            self,
                            exc_info=e,
                        )
                        remove_check = True
                if remove_check:
                    TCTaskManager.add_tombstone(self.name)
                self.is_running = False
                if not remove_check:
                    TCTaskManager.set_standby(self.name)
            else:
                pass
                # Print the time until next run
                # time_until = self.to_run_next - dt.now()
                # gui.gprint(f"{self.name} not ready. Next run in {time_until}")

        self.wrapper = wrapper
        return wrapper

    def __call__(self) -> CoroutineWrap:
        """
        Decorator for wrapping a coroutine function with the TCTask scheduling logic.

        Args:
            func (coroutine function): The coroutine function to wrap.

        Returns:
            The wrapped coroutine function.
        """

        return self.wrapper()

    def next_run(self) -> dt:
        """
        Calculates the dt of the next time the task should run
        based on the current time, last_run, and time_interval.

        Returns:
            The dt of the next time the task should be run.
        """
        # Calculate the next future occurrence
        next_occurrence = self.time_interval.after(
            dt.now().replace(second=0, microsecond=0)
        )
        return next_occurrence

    def __str__(self) -> str:
        st = f"{self.name},{self.status},{self.time_left_shorter()}"
        return st

    def __repr__(self) -> str:
        st = f"{self.name},{self.status},{self.time_left_shorter()}"
        return st


class TCTaskManager:
    """
    Manager class for every TCTask object.
    Handles running all tasks and organizing a priority queue of all
    the tasks in order.

    Attributes:
        tasks (dict): A dictionary of all TCTask objects managed by the manager.
        to_delete(list): a list of TCTask object to delete, since.
    """

    # This is about as fast as I can make it.
    _instance = None

    @classmethod
    def get_instance(cls):
        """Get or create the TC Task Manager."""
        if cls._instance is None:
            cls._instance = TCTaskManager()
        return cls._instance

    def __init__(self):
        self.tasks: Dict[str, TCTask] = {}
        self.to_delete = []
        self.myqueue: AutoRebalancePriorityQueue[TCTaskRef] = (
            AutoRebalancePriorityQueue()
        )

    @classmethod
    def get_task(cls, name):
        """
        Check if a TCTask object with the specified name is in the list of tasks.
        Args:
            name (str): The name of the TCTask object to find in the list of tasks.

        Returns:
            True if a task is already there, False if no matching task was found.
        """
        manager = cls.get_instance()
        if name in manager.tasks:
            return manager.tasks[name]
        return None

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
    def change_task_time(cls, name, dat):
        """
        Check if a TCTask object with the specified name is in the list of tasks.
        Args:
            name (str): The name of the TCTask object to find in the list of tasks.

        Returns:
            True if a task is already there, False if no matching task was found.
        """
        manager = cls.get_instance()
        if name in manager.tasks:
            manager.tasks[name].to_run_next = dat
            manager.myqueue.rebalance()
            return True
        return False

    @classmethod
    def change_task_interval(cls, name, new_rrule):
        """
        Check if a TCTask object with the specified name is in the list of tasks.
        Args:
            name (str): The name of the TCTask object to find in the list of tasks.

        Returns:
            True if a task is already there, False if no matching task was found.
        """
        manager = cls.get_instance()
        if name in manager.tasks:
            manager.tasks[name].time_interval = new_rrule
            manager.tasks[name].to_run_next = manager.tasks[name].next_run()
            manager.myqueue.rebalance()
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
        logs.warning("added task %s ", task.name)
        manager = cls.get_instance()
        manager.tasks[task.name] = task
        TCTaskManager.set_standby(task.name)

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
            logs.warning("removing task", name)
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
        logs.warning("%s is running", name)
        manager.tasks[name].status = "running"
        # manager.to_delete.append(name)

    @classmethod
    def set_standby(cls, name):
        """
        Set task name into standby mode, readd to priority queue
        Args:
            name (str): The name of the task to standby
        """
        manager = cls.get_instance()

        logs.warning("%s is standby", name)
        to_add = manager.tasks[name]
        if (to_add.status != "standby") and (name not in manager.to_delete):
            manager.myqueue.put(to_add.get_ref())
            to_add.status = "standby"
        # manager.to_delete.append(name)

    @classmethod
    def task_check(cls):
        """
        Check how much time left each task has.
        """
        # Check each task to see if it's time to run
        manager = TCTaskManager.get_instance()
        task_string_list = []
        for _, task in manager.tasks.items():
            task_string_list.append(task.time_left() + "\n")
        return task_string_list

    @classmethod
    def get_task_status(cls):
        """get a small string that shows the current number of scheduled and running tasks."""
        manager = TCTaskManager.get_instance()
        running = scheduled = 0
        deltas = []
        output = output2 = ""
        sorted_dict = sorted(
            manager.tasks.items(), key=lambda x: x[1].get_total_seconds_until()
        )
        for _, task in sorted_dict:
            output2 += task.time_left_short()
            if task.is_running:
                running += 1
            else:
                scheduled += 1
                deltas.append(task.to_run_next - dt.now())

        if running > 0:
            output += f"Running:{running}, "
        if scheduled > 0:
            output += f"Scheduled:{scheduled}, "
        if deltas:
            nextt = min(deltas, key=lambda x: x.total_seconds())
            days = hours = mins = ""
            if nextt.days > 0:
                days = str(nextt.days) + "d,"
            if (nextt.seconds // 3600) > 0:
                hours = str(int(nextt.seconds // 3600)) + "h,"
            if ((nextt.seconds // 60) % 60) > 0:
                mins = str(int((nextt.seconds // 60) % 60)) + "m"
            formatted_delta = f"next auto task in {days}{hours}{mins}"
            output += formatted_delta
        return output, output2

    @staticmethod
    async def run_tasks():
        """
        Check for the tasks that can be run at this specific time, and runs them.
        """
        # Check each task to see if it's time to run
        manager = TCTaskManager.get_instance()
        for name in manager.to_delete:
            task = manager.tasks.get(name, None)
            if task is None:
                continue
            if task.is_running is False:
                TCTaskManager.remove_task(task.name)
        manager.to_delete = []

        while not manager.myqueue.empty():
            gui.DataStore.set(
                "queuenext", manager.myqueue.queue[0].get_task().time_left_shorter()
            )
            if manager.myqueue.queue[0].get_task().can_i_run():
                task = manager.myqueue.get().get_task()
                asyncio.create_task(task())
            else:
                break

        # Wait for 1 second before checking again
        await asyncio.sleep(1)
