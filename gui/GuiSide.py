import time
import tkinter as tk
from tkinter import ttk
import asyncio
from queue import Queue
from .BotEntry import DataStore
import threading
queued = Queue()
def gprint(*args, **kwargs):
    print(*args, **kwargs)
    s=""
    #for arg in args:    s+=str(arg)
    #queued.put(str(s))



class Gui:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Nikki Panel")
        self.runok=True
        self.label_dict = {
            'con': 'True'  # Default value is True
        }
        framestack = tk.Frame(self.window)
        
        labels = tk.Label(framestack, text="Label s")
        labels.pack()
        self.label_dict['con'] = labels

        label1 = tk.Label(framestack, text="Label 1")
        label1.pack()
        self.label_dict['4'] = label1

        label2 = tk.Label(framestack, text="Label 2")
        label2.pack()
        self.label_dict['3'] = label2

        frame = tk.Frame(framestack)
        frame.pack()
        labo1 = tk.Label(frame, text="Latency")
        labo1.pack(side='left')
        latency_label = tk.Label(frame, text="Latency")
        latency_label.pack(side='right')
        self.label_dict['latency'] = latency_label

        tasknum_label = tk.Label(framestack, text="Task Number")
        tasknum_label.pack()
        self.label_dict['tasknum'] = tasknum_label

        schedule_label = tk.Label(self.window, text="Schedule")
        schedule_label.pack(side=tk.RIGHT)
        self.label_dict['schedule'] = schedule_label
        framestack.pack(side='right')
        commands_label = tk.Label(self.window, text="Commands")
        commands_label.pack(side=tk.RIGHT)
        self.label_dict['commands'] = commands_label

    async def kill(self):
        self.runok=False
        self.window.destroy()

    async def update_gui_labels(self):
       
        for key, value in DataStore.db.items():
            # Update the label values based on the data dictionary
            if key in self.label_dict:
                self.label_dict[key]['text'] = str(value)
                self.window.update()
                await asyncio.sleep(0.1)

    async def update_every_second(self):
        while self.runok:
            await self.update_gui_labels()
            await asyncio.sleep(1)
            self.window.update()
            await asyncio.sleep(.1)
        else:
            self.window.destroy()

    def run(self, loop):

        # Create and run the event loop
        #loop = asyncio.get_event_loop()
        loop.create_task(self.update_every_second())
        #loop.run_forever()
        # Start the Tkinter event loop
        

# Create and run the application
#app = Gui()
#app.run()
