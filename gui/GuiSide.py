import tkinter as tk
import logging
import asyncio
from queue import Queue
from typing import TextIO
from .BotEntry import DataStore
from datetime import datetime
import tkinter.font as font

logs = logging.getLogger("TCLogger")
queued = Queue()


GUI_MODE = False
DEBUG_MODE = False


def toggle_debug_mode(mode: bool):
    print("DEBUG MODE IS ON.")
    global DEBUG_MODE
    DEBUG_MODE = mode


def special_string_split(string, max_length):
    words = string.split()  # Split the string into individual words
    result = []
    current_entry = ""
    for word in words:
        if len(current_entry) + len(word) <= max_length:
            current_entry += word + " "
        else:
            result.append(current_entry.strip())
            current_entry = word + " "
    result.append(current_entry.strip())

    return result


current_list = []


def dprint(*args, **kwargs):
    if DEBUG_MODE:
        gprint(*args, **kwargs)


def gprint(
    *values: object,
    sep: str | None = " ",
    end: str | None = "\n",
    file: TextIO | None = None,
    flush: bool = False,
):
    message = sep.join(map(str, values))
    print(*values, sep=sep, end=end, file=file, flush=flush)
    logs.info(message)
    s = ""
    if not GUI_MODE:
        return
    for arg in values:
        s += str(arg)
    lines = f"•{str(s)}".split("\n")
    splitted_lines = []
    for line in lines:
        splitted_lines.extend(
            special_string_split(line, 80)
        )  # Apply special_string_split to each line

    for entry in splitted_lines:
        queued.put(str(entry))


MAX_SIZE = 52


class Gui:
    def __init__(self):
        global GUI_MODE
        GUI_MODE = True
        self.window = tk.Tk()
        fontv = font.Font(size=8)
        self.window.title("Nikki Panel")
        self.runok = True
        # self.window.geometry("512x400")
        self.label_dict = {
            "con": "True",  # Default value is True
            "time": "00:00",
        }
        self.current_list = []

        # Use grid layout manager for the framestack
        framestack = tk.Frame(self.window)
        framestack.grid(row=0, column=2, sticky="nsew")

        # Use grid layout manager for lt label in mframe
        lt = tk.Label(framestack, text="Time")
        lt.grid(row=0, column=0)

        # Use grid layout manager for labelts label in mframe
        labelts = tk.Label(framestack, text="thetime")
        labelts.grid(row=0, column=1)
        self.label_dict["time"] = labelts

        # Use grid layout manager for labels label in framestack
        labels = tk.Label(framestack, text="Label s")
        labels.grid(row=1, column=0)
        self.label_dict["con"] = labels
        # Use grid layout manager for labels label in framestack
        queuenext = tk.Label(framestack, text="Firsttimevalue")
        queuenext.grid(row=1, column=1)
        self.label_dict["queuenext"] = queuenext

        labo1 = tk.Label(framestack, text="Latency")
        labo1.grid(row=4, column=0)

        latency_label = tk.Label(framestack, text="Latency")
        latency_label.grid(row=4, column=1)
        self.label_dict["latency"] = latency_label
        labo1 = tk.Label(framestack, text="TaskNum")
        labo1.grid(row=3, column=0)

        tasknum_label = tk.Label(framestack, text="Task Number")
        tasknum_label.grid(row=3, column=1)
        self.label_dict["tasknum"] = tasknum_label
        rootframe = tk.Frame(self.window)
        # canvas = tk.Canvas(rootframe)
        scrollbar = tk.Scrollbar(rootframe, orient="vertical")

        self.major_events = tk.Text(rootframe, padx=10, wrap="word", font=fontv)
        # scrollable_frame = ttk.Frame(canvas)

        self.major_events.pack(side="left", fill="y", expand=True)
        scrollbar.pack(side="right", fill="y")
        scrollbar.config(command=self.major_events.yview)
        self.major_events.config(yscrollcommand=scrollbar.set)
        rootframe.grid(row=1, column=0, columnspan=4)

        schedule_label = tk.Label(self.window, text="Schedule", font=fontv)
        schedule_label.grid(row=0, column=3, sticky="e")
        self.label_dict["schedule"] = schedule_label

        commands_label = tk.Label(self.window, text="Commands")
        commands_label.grid(row=0, column=1, sticky="e")
        self.label_dict["commands"] = commands_label

        # self.window.grid_columnconfigure(0, minsize=256)
        self.window.grid_columnconfigure(1, minsize=128)
        self.window.grid_columnconfigure(2, minsize=128)
        self.window.grid_columnconfigure(3, minsize=128)

    async def kill(self):
        self.runok = False
        self.window.destroy()

    async def update_gui_labels(self):
        self.label_dict["time"]["text"] = datetime.now().strftime("%H:%M:%S.%f")[:-4]
        if not queued.empty():
            value = queued.get(block=False)
            if len(self.current_list) > MAX_SIZE:
                self.current_list.pop(0)
            else:
                pass
                # self.major_events.configure(height=len(self.current_list))
            self.current_list.append(value)
            outputlog = "\n".join(self.current_list)

            self.major_events.delete("1.0", "end")
            self.major_events.insert("end", outputlog)
            self.major_events.yview_moveto(1.0)
        if not DataStore.cqueue.empty():
            key, value = DataStore.cqueue.get(block=False)
            if key in self.label_dict:
                self.label_dict[key]["text"] = str(value)
                self.window.update()
                await asyncio.sleep(0.1)

    async def update_every_second(self):
        while self.runok:
            await self.update_gui_labels()
            self.window.update()
            await asyncio.sleep(0.1)
        else:
            self.window.destroy()

    def run(self, loop):
        # Create and run the event loop
        # loop = asyncio.get_event_loop()
        loop.create_task(self.update_every_second())
        # loop.run_forever()
        # Start the Tkinter event loop


# Create and run the application
# app = Gui()
# app.run()
