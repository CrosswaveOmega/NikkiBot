from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker, Session


import logging

'''
The database engine is stored within a DatabaseSingleton, that ensures only one engine is connected to
at any given time.  

This way, it can be accessed from anywhere, and not just through the Bot object.

'''

class DatabaseSingleton:
    """A singleton storage class that stores the database engine and connection objects."""


    class __DatabaseSingleton:
        def __init__(self, arg, db_name='./saveData/mydatabase.db'):


            file_handler = logging.FileHandler("./logs/sqlalchemy.log")
            # create a logger and set its level to INFO
            self.logger = logging.getLogger("sqlalchemy.engine")
            self.logger.setLevel(logging.INFO)

            # add the file handler to the logger
            self.logger.addHandler(file_handler)
            self.bases=[]
            self.val = arg
            self.database_name=db_name
            self.connected=False
            self.engine=None
            self.SessionLocal: sessionmaker = None
            self.session: Session = None
            

        def connect_to_engine(self):
            if not self.connected:
                db_name=self.database_name
                self.engine = create_engine(f'sqlite:///{db_name}', echo=False)
                for base in self.bases:
                    base.metadata.create_all(self.engine)
                self.connected=True
                SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=True)


                self.SessionLocal: sessionmaker = SessionLocal
                self.session: Session = self.SessionLocal()
                self.session.commit()

        def load_in_base(self,Base):
            print("loading in: ",Base.__name__)
            if not Base in self.bases: self.bases.append(Base)
            print('done')
            if self.connected:
                Base.metadata.create_all(self.engine)
                self.session: Session = self.SessionLocal()
                self.session.commit()

        def start_up(self):

            SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=True)
            
            self.SessionLocal: sessionmaker = SessionLocal
            self.session: Session = None

        def print_arg(self):
            print(self.val)


        def execute_sql_string(self, string):
            with self.get_session() as session:
                session.execute(text(string))
   
        def close(self):
            if self.session is not None:
                self.session.close()
            self.engine.dispose()
            self.connected=False

        def get_session(self) -> Session:
            if not self.session:
                self.session = self.SessionLocal()
            return self.session

    _instance = None

    def __init__(self, arg, **kwargs):
        if not DatabaseSingleton._instance:
            print("Running singleton 2")
            session = self.__DatabaseSingleton(arg, **kwargs)
            DatabaseSingleton._instance = session
        #If it's made, do nothing.
        
    def startup(self):
        self._instance.connect_to_engine()

    def execute_sql_string(self, sqlstring):
        '''Execute a SQL String.'''
        self._instance.execute_sql_string(sqlstring)
    def get_metadata(self):
        # get metadata of database
        metadata = MetaData()
        metadata.reflect(bind=self._instance.engine)
        return metadata

    def load_base(self, Base):
        self._instance.load_in_base(Base)
    # Use a static method to get the singleton instance.

    @staticmethod
    def get_instance():
        if not DatabaseSingleton._instance:
            # Raise an exception if the singleton instance has not been created yet.
            raise Exception("Singleton instance does not exist")
        return DatabaseSingleton._instance

    def commit(self):
        if not DatabaseSingleton._instance:
            # Raise an exception if the singleton instance has not been created yet.
            raise Exception("Singleton instance does not exist")
        DatabaseSingleton._instance.get_session().commit()
    
    def close_out(self):
        inst=self.get_instance()
        inst.close()

    @staticmethod
    def get_session() -> Session:
        inst = DatabaseSingleton.get_instance()
        return inst.get_session()