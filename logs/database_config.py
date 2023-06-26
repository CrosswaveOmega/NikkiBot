from sqlalchemy import Column, String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .database_singleton import DatabaseSingleton

Base = declarative_base()

class KeyDict(Base):
    __tablename__ = 'keydict'

    index = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True)
    type = Column(String(20))
    switch = relationship('GlobalSwitch', backref='keydict', uselist=False, cascade='all, delete-orphan')
    variable = relationship('GlobalVariable', backref='keydict', uselist=False, cascade='all, delete-orphan')
    string = relationship('GlobalString', backref='keydict', uselist=False, cascade='all, delete-orphan')

class GlobalSwitch(Base):
    __tablename__ = 'global_switch'

    index = Column(Integer, ForeignKey('keydict.index'), primary_key=True)
    key = Column(String(255), unique=True)
    value = Column(Boolean)
    comment = Column(String(255))

    def set_value(self, value, comment=''):
        self.value = value
        if comment!='':
            self.comment = comment

    def get_value(self):
        return self.value

class GlobalVariable(Base):
    __tablename__ = 'global_variable'

    index = Column(Integer, ForeignKey('keydict.index'), primary_key=True)
    key = Column(String(255), unique=True)
    value = Column(Integer)
    comment = Column(String(255))

    def set_value(self, value, comment=''):
        self.value = value
        if comment!='':
            self.comment = comment


    def get_value(self):
        return self.value

class GlobalString(Base):
    __tablename__ = 'global_string'

    index = Column(Integer, ForeignKey('keydict.index'), primary_key=True)
    key = Column(String(255), unique=True)
    value = Column(String(255))
    comment = Column(String(255))

    def set_value(self, value, comment=''):
        self.value = value
        if comment!='':
            self.comment = comment


    def get_value(self):
        return self.value

class GlobalData:

    @staticmethod
    def set_value(key, value, comment=''):
        session = DatabaseSingleton.get_session()
        key_dict = session.query(KeyDict).filter_by(key=key).first()

        if key_dict:
            if key_dict.type == 'switch':
                switch = key_dict.switch
                switch.set_value(value, comment)
            elif key_dict.type == 'variable':
                variable = key_dict.variable
                variable.set_value(value, comment)
            elif key_dict.type == 'string':
                string = key_dict.string
                string.set_value(value, comment)
        else:
            if isinstance(value, bool):
                switch = GlobalSwitch(key=key, value=value, comment=comment)
                key_dict = KeyDict(key=key, type='switch', switch=switch)
            elif isinstance(value, int):
                variable = GlobalVariable(key=key, value=value, comment=comment)
                key_dict = KeyDict(key=key, type='variable', variable=variable)
            elif isinstance(value, str):
                string = GlobalString(key=key, value=value, comment=comment)
                key_dict = KeyDict(key=key, type='string', string=string)
            else:
                raise ValueError("Unsupported data type")

            session.add(key_dict)

        session.commit()
    @staticmethod
    def get(key):
        return GlobalData.get(key)
    @staticmethod
    def get_value(key):
        session = DatabaseSingleton.get_session()
        key_dict = session.query(KeyDict).filter_by(key=key).first()

        if key_dict:
            if key_dict.type == 'switch':
                switch = key_dict.switch
                return switch.get_value()
            elif key_dict.type == 'variable':
                variable = key_dict.variable
                return variable.get_value()
            elif key_dict.type == 'string':
                string = key_dict.string
                return string.get_value()
        else:
            return None


DatabaseSingleton('mainsetup').load_base(Base)