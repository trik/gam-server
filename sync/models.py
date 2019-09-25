from sqlalchemy import (
    Column, Integer, String
)

from gam.database import Base


class Change(Base):
    __tablename__ = 'sync_change'

    id = Column(Integer, primary_key=True)
    table_name = Column(String(100), nullable=False)
    object_id = Column(Integer, nullable=False)
    entry_type = Column(String(20), nullable=False)
