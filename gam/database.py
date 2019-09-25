""" This module exports the database engine.
Notes:
     Using the scoped_session contextmanager is
     best practice to ensure the session gets closed
     and reduces noise in code by not having to manually
     commit or rollback the db if a exception occurs.
"""
from contextlib import contextmanager

from sqlalchemy import Boolean, Column, create_engine
from sqlalchemy.ext.declarative import declared_attr, declarative_base
from sqlalchemy.orm import sessionmaker

from .settings import DATABASE_URL

try:
    import __pypy__  # noqa
    from psycopg2cffi import compat
    compat.register()
except ImportError:
    pass


engine = create_engine(DATABASE_URL)

# Session to be used throughout app.
Session = sessionmaker(bind=engine)

class BaseModel:
    @declared_attr
    def __tablename__(self):
        return self.__name__.lower()

class SoftDelete:
    deleted = Column(Boolean(), server_default='FALSE', nullable=False)

class Fixed:
    fixed = Column(Boolean(), server_default='FALSE', nullable=False)


Base = declarative_base(cls=BaseModel)

@contextmanager
def scoped_session() -> Session:
    session = Session()
    try:
        yield session
        session.commit()
    except:  # noqa
        session.rollback()
        raise
    finally:
        session.close()
