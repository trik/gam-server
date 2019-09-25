from sqlalchemy import (
    Column, Integer, String
)

from gam.database import Base, SoftDelete


class Project(Base, SoftDelete):
    __tablename__ = 'projects_project'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False)
