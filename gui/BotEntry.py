
import subprocess
import asyncio
from queue import Queue
class DataStore:
    db = None
    init=None
    lock=None
    cqueue=None
    @staticmethod
    def initialize(database=None):
       DataStore.db={}
       DataStore.lock=asyncio.Lock()
       DataStore.cqueue=Queue()
        

    @staticmethod
    def initialize_default_values():
        default_values = {
            'latency': 0.04,
            'con': True,
            'tasknum': 0,
            'schedule': [],
            'commands': []
        }
        for k, v in default_values.items():
            DataStore.add_value(k,v)
        #DataStore.db.update(default_values)

        
    @staticmethod
    def add_value(key, value):
        old=None
        if key in DataStore.db:
            old=DataStore.db[key]
        
        DataStore.db[key] = value
        if old!=value:
            DataStore.cqueue.put_nowait((key,value))


    @staticmethod
    def set(key, value):
        DataStore.add_value(key,value)

    @staticmethod
    def update_value(key, value):
        if key in DataStore.db:
            DataStore.add_value(key,value)

    @staticmethod
    def remove_value(key):
        if key in DataStore.db:
            del DataStore.db[key]

    @staticmethod
    def closeout():
        DataStore.db['con']=False
