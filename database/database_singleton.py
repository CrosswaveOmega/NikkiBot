from typing import Dict
import gui
from sqlalchemy import Engine, create_engine, MetaData
from sqlalchemy.orm import sessionmaker, Session

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine

import logging
from .db_compare_utils import compare_db, async_compare_db

"""
The database engine is stored within a DatabaseSingleton, that ensures only one engine is connected to
at any given time.  

This way, it can be accessed from anywhere, and not just through the Bot object.

It also can add new columns to the engine if they're missing,
but that's the extent of database alterations.
"""

# TO DO LATER: ADD AN ASYNC SESSION MODE.


def generate_column_definition(column, engine):
    column_name = column.name
    column_type = column.type.compile(engine.dialect)
    column_attributes = [str(attr) for attr in column.constraints]
    column_definition = f"{column_name} {column_type}"
    if column_attributes:
        column_definition += " " + " ".join(column_attributes)
    return column_definition


ENGINEPREFIX = "sqlite:///"
ASYNCENGINE = "sqlite+aiosqlite:///"


class EngineContainer:
    """This class contains the database urls and the active engines."""

    def __init__(self, db_name, asyncmode=False):
        self.database_name = db_name
        self.connected = False
        self.async_mode = asyncmode
        self.engine: Engine = None
        self.aengine: AsyncEngine = None
        self.bases = []
        self.SessionLocal: sessionmaker = None
        self.sync_sessions: Dict[str, Session] = {}
        self.SessionAsyncLocal: async_sessionmaker = None

    def connect_to_engine(self):
        if not self.connected:
            db_name = self.database_name
            self.engine = create_engine(f"{ENGINEPREFIX}{db_name}", echo=False)
            for base in self.bases:
                base.metadata.create_all(self.engine)
            self.connected = True
            SessionLocal = sessionmaker(
                bind=self.engine, autocommit=False, autoflush=True
            )

            self.SessionLocal: sessionmaker = SessionLocal

            result = self.compare_db()
            gui.gprint(result)

    async def connect_to_engine_a(self):
        """async variant of connect_to_engine."""
        if not self.connected and self.async_mode:
            gui.print("Connecting to ASYNCIO compatible engine variant.")
            db_name = self.database_name
            self.aengine = create_async_engine(f"{ASYNCENGINE}{db_name}", echo=False)
            self.SessionAsyncLocal = async_sessionmaker(
                bind=self.aengine, autocommit=False, autoflush=True
            )
            for base in self.bases:
                async with self.aengine.begin() as conn:
                    await conn.run_sync(base.metadata.create_all)
            self.connected = True

    async def sync_bases(self):
        if self.connected and self.async_mode:
            for base in self.bases:
                async with self.aengine.begin() as conn:
                    await conn.run_sync(base.metadata.create_all)
        elif self.connected:
            for base in self.bases:
                base.metadata.create_all(self.engine)

    def load_in_base(self, Base):
        gui.dprint("loading in: ", Base.__name__, Base)
        if Base not in self.bases:
            self.bases.append(Base)
        # if self.connected:    Base.metadata.create_all(self.engine)

    def close(self):
        for i, v in self.sync_sessions.items():
            v.close()
        self.engine.dispose()
        self.connected = False

    async def close_async(self):
        if self.connected and self.async_mode:
            await self.aengine.dispose()
            gui.dprint("disposed")
            self.connected = False

    def get_session(self, session_name: str = "any") -> Session:
        if session_name not in self.sync_sessions:
            self.sync_sessions[session_name] = self.SessionLocal()
        # if not self.session:     self.session = self.SessionLocal()

        return self.sync_sessions[session_name]

    def get_sub_session(self) -> Session:
        return self.SessionLocal()

    def get_async_session(self) -> AsyncSession:
        mysession = self.SessionAsyncLocal()
        return mysession

    def compare_db(self):
        """compare current metadata with sqlalchemy metadata"""

        return compare_db(self)

    async def compare_db_async(self):
        """compare current metadata with sqlalchemy metadata"""
        return await async_compare_db(self)


class DatabaseSingleton:
    """A singleton storage class that stores the database engine and connection objects."""

    class _DatabaseSingleton:
        def __init__(
            self,
            arg,
            db_name="./saveData/mydatabase.db",
            adbname="./saveData/asyncmydatabase.db",
        ):
            file_handler = logging.FileHandler(
                "./logs/sqlalchemy.log", encoding="utf-8"
            )
            # create a logger and set its level to INFO

            self.bases = []
            self.engines: Dict[str, EngineContainer] = {}
            self.val = arg
            self.database_name = db_name
            self.adatabase_name = adbname
            self.connected, self.connected_a = False, False
            self.engine = None
            self.aengine = None
            self.SessionLocal: sessionmaker = None
            self.SessionAsyncLocal: async_sessionmaker = None
            self.session: Session = None
            self.add_engine("main", db_name)
            self.add_engine("async", adbname, True)

        def add_engine(self, ename, db_name, mode=False):
            if ename not in self.engines:
                engine = EngineContainer(db_name, mode)
                self.engines[ename] = engine

        def load_in_base(self, Base, ename=None):
            gui.dprint("loading in: ", Base.__name__, Base)
            if ename:
                if ename in self.engines:
                    self.engines[ename].load_in_base(Base)
            else:
                for en in self.engines.keys():
                    self.engines[en].load_in_base(Base)
            if Base not in self.bases:
                self.bases.append(Base)

        async def startup_all(self):
            for en, val in self.engines.items():
                if val.async_mode:
                    await val.connect_to_engine_a()
                else:
                    val.connect_to_engine()

        async def sync_all(self):
            for en, val in self.engines.items():
                await val.sync_bases()

        def print_arg(self):
            gui.dprint(self.val)

        async def compare_db(self):
            """compare current metadata with sqlalchemy metadata"""
            for en, val in self.engines.items():
                if val.async_mode:
                    await val.compare_db_async()
                else:
                    val.compare_db()
            return

        async def close_async(self):
            for en, val in self.engines.items():
                if val.async_mode:
                    await val.close_async()
                else:
                    val.close()

        def get_session(self, mode: str = "any") -> Session:
            for en, val in self.engines.items():
                if not val.async_mode:
                    return val.get_session(mode)

        def get_sub_session(self) -> Session:
            for en, val in self.engines.items():
                if not val.async_mode:
                    return val.get_sub_session()

        def get_async_session(self) -> AsyncSession:
            for en, val in self.engines.items():
                if val.async_mode:
                    return val.get_async_session()

    _instance: _DatabaseSingleton = None

    def __init__(self, arg, **kwargs):
        if not DatabaseSingleton._instance:
            gui.dprint("Running singleton 2")
            instance = self._DatabaseSingleton(arg, **kwargs)
            DatabaseSingleton._instance = instance

    async def database_check(self):
        await self._instance.compare_db()

    async def startup_all(self):
        await self._instance.startup_all()

    def get_metadata(self):
        # get metadata of database
        for en, val in self._instance.engines.items():
            if not val.async_mode:
                metadata = MetaData()
                metadata.reflect(bind=val.engine)
                return metadata

    def load_base(self, Base):
        """Load in a Declarative base."""
        print("Loading base ", Base)
        self._instance.load_in_base(Base)

    def load_base_to(self, Base, ename: str):
        """load a declarative base to a specific engine."""
        self._instance.load_in_base(Base, ename)

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

    async def close_out(self):
        inst = self.get_instance()

        await inst.close_async()

    @staticmethod
    def get_session(mode: str = "any") -> Session:
        inst = DatabaseSingleton.get_instance()
        return inst.get_session(mode)

    @staticmethod
    def get_new_session() -> Session:
        inst = DatabaseSingleton.get_instance()
        return inst.get_sub_session()

    @staticmethod
    def get_async_session() -> AsyncSession:
        inst = DatabaseSingleton.get_instance()
        session = inst.get_async_session()
        return session


class DSCTX:
    def __init__(self):
        self._instance = DatabaseSingleton._DatabaseSingleton("setup")
