import time
import tkinter as tk
from tkinter import ttk
import asyncio
from queue import Queue
from .BotEntry import DataStore
import threading
from datetime import datetime
queued = Queue()

current_list=[]
def gprint(*args, **kwargs):
    print(*args, **kwargs)
    s=""
    for arg in args:    s+=str(arg)
    sp=str(s).split('\n')
    for se in sp:    queued.put(str(se))



class Gui:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Nikki Panel")
        self.runok = True
        #self.window.geometry("512x400")
        self.label_dict = {
            'con': 'True',  # Default value is True
            'time': '00:00',
        }
        self.current_list = []
        
        # Use grid layout manager for the framestack
        framestack = tk.Frame(self.window)
        framestack.grid(row=0, column=2, sticky='nsew')
        
        
        # Use grid layout manager for lt label in mframe
        lt = tk.Label(framestack, text="Time")
        lt.grid(row=0, column=0)
        
        # Use grid layout manager for labelts label in mframe
        labelts = tk.Label(framestack, text="thetime")
        labelts.grid(row=0, column=1)
        self.label_dict['time'] = labelts
        
        # Use grid layout manager for labels label in framestack
        labels = tk.Label(framestack, text="Label s")
        labels.grid(row=1, column=0)
        self.label_dict['con'] = labels

        
        labo1 = tk.Label(framestack, text="Latency")
        labo1.grid(row=4, column=0)
        

        latency_label = tk.Label(framestack, text="Latency")
        latency_label.grid(row=4, column=1)
        self.label_dict['latency'] = latency_label
        
        tasknum_label = tk.Label(framestack, text="Task Number")
        tasknum_label.grid(row=3, column=0)
        self.label_dict['tasknum'] = tasknum_label

        self.major_events = tk.Text(self.window, wrap='word', font=('Arial', 6),width=64,height=32)
        self.major_events.grid(row=0, column=0)

        schedule_label = tk.Label(self.window, text="Schedule")
        schedule_label.grid(row=0, column=3, sticky='e')
        self.label_dict['schedule'] = schedule_label
        
        commands_label = tk.Label(self.window, text="Commands")
        commands_label.grid(row=0, column=1, sticky='e')
        self.label_dict['commands'] = commands_label

        #self.window.grid_columnconfigure(0, minsize=256)
        self.window.grid_columnconfigure(1, minsize=128)
        self.window.grid_columnconfigure(2, minsize=128)
        self.window.grid_columnconfigure(3, minsize=128)

    async def kill(self):
        self.runok=False
        self.window.destroy()

    async def update_gui_labels(self):
       self.label_dict['time']['text']=datetime.now().strftime("%H:%M:%S.%f")[:-4]
       if not queued.empty():
            value =queued.get(block=False)
            if len(self.current_list)>16:
               self.current_list.pop(0)
            self.current_list.append(value)
            outputlog='\n'.join(self.current_list)
            self.major_events.delete('1.0', 'end')
            self.major_events.insert('end', outputlog)
       if not DataStore.cqueue.empty():
           key, value =DataStore.cqueue.get(block=False)
           if key in self.label_dict:
                self.label_dict[key]['text'] = str(value)
                self.window.update()
                #await asyncio.sleep(0.4)


    async def update_every_second(self):
        while self.runok:
            await self.update_gui_labels()
            self.window.update()
            await asyncio.sleep(0.1)
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
