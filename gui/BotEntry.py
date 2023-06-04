
import subprocess

class DataStore:
    db = None
    init=None
    @staticmethod
    def initialize(database=None):
       DataStore.db={}
        

    @staticmethod
    def initialize_default_values():
        default_values = {
            'latency': 0.04,
            'con': True,
            'tasknum': 0,
            'schedule': [],
            'commands': []
        }
        DataStore.db.update(default_values)

        
    @staticmethod
    def add_value(key, value):
        DataStore.db[key] = value

    @staticmethod
    def set(key, value):
        DataStore.db[key] = value

    @staticmethod
    def update_value(key, value):
        if key in DataStore.db:
            DataStore.db[key] = value

    @staticmethod
    def remove_value(key):
        if key in DataStore.db:
            del DataStore.db[key]

    @staticmethod
    def closeout():
        DataStore.db['con']=False
