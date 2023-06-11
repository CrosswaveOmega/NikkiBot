import gui
from sqlalchemy import create_engine, text, MetaData, Table, inspect, Column
from sqlalchemy.orm import sessionmaker, Session

from sqlalchemy.orm import registry

import logging

'''
The database engine is stored within a DatabaseSingleton, that ensures only one engine is connected to
at any given time.  

This way, it can be accessed from anywhere, and not just through the Bot object.

It also can add new columns to the engine if they're missing,
but that's the extent of database alterations.
'''

def generate_column_definition(column, engine):
    column_name = column.name
    column_type = column.type.compile(engine.dialect)
    column_attributes = [str(attr) for attr in column.constraints]
    column_definition = f"{column_name} {column_type}"
    if column_attributes:
        column_definition += " " + " ".join(column_attributes)
    return column_definition

# Generate the ALTER TABLE statemen
class DatabaseSingleton:
    """A singleton storage class that stores the database engine and connection objects."""


    class __DatabaseSingleton:
        def __init__(self, arg, db_name='./saveData/mydatabase.db'):


            file_handler = logging.FileHandler("./logs/sqlalchemy.log", encoding='utf-8')
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
                result=self.compare_db()
                gui.gprint(result)

        def load_in_base(self,Base):
            print("loading in: ",Base.__name__,Base)
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

        def compare_db(self):
            '''compare current metadata with sqlalchemy metadata'''
            def merge_metadata(*original_metadata) -> MetaData:
                merged = MetaData()

                for original_metadatum in original_metadata:
                    for table in original_metadatum.tables.values():
                        table.to_metadata(merged)

                return merged

            insp = inspect(self.engine)
            
            db_meta = MetaData()
            db_meta.reflect(bind=self.engine)

            mt = [base.metadata for base in self.bases]
            merged = merge_metadata(*mt)
            
            # Get the tables from the metadata objects
            tables1 = db_meta.tables
            tables2 = merged.tables

            # Compare tables
            result=""
            session=self.get_session()
            for table_name in set(tables1) | set(tables2):
                table1 = tables1.get(table_name)
                table2 = tables2.get(table_name)
                if table1 is None:
                    result+=(f"Table '{table_name}' is missing from remote.\n")
                    continue
                if table2 is None:
                    result+=(f"Table '{table_name}' is missing from local.\n")
                    continue

                columns1 = insp.get_columns(table_name, schema=table1.schema)

                columns2 = [
                    {
                        'name': column.name,
                        'type': column.type,
                        'nullable': column.nullable,
                        'origcol':column
                    }
                    for column in table2.columns
                ]

                column_names1 = set(column['name'] for column in columns1)
                column_names2 = set(column['name'] for column in columns2)

                missing_columns_table2 = column_names1 - column_names2
                missing_columns_table1 = column_names2 - column_names1

                # Print missing columns
                if missing_columns_table2:
                    result+=(f"Missing columns in local '{table_name}': {', '.join(missing_columns_table2)}\n")
                if missing_columns_table1:
                    result+=(f"Missing columns in remote '{table_name}': {', '.join(missing_columns_table1)}\n")
                    for miss in missing_columns_table1:
                        #Add missing columns to remote.
                        #WARNING: UNSTABLE
                        col:Column=table2.columns[miss]
                        alter_table_stmt = text(f"ALTER TABLE {table_name} ADD COLUMN {generate_column_definition(col,self.engine)};")
                        session.execute(alter_table_stmt)
                        session.commit()
            return result







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
    def database_check(self):
        return self._instance.compare_db()
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