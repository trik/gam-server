from sqlalchemy import (
    Column, ForeignKey, Integer, String, Text
)

from gam.database import Base, SoftDelete
from projects.models import Project

class Epic(Base, SoftDelete):
    __tablename__ = 'agile_epic'

    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey(Project.id), nullable=False)
    name = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, server_default='0')

class UserStory(Base, SoftDelete):
    __tablename__ = 'agile_user_story'

    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey(Project.id), nullable=False)
    epic_id = Column(ForeignKey(Epic.id), nullable=True)
    name = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, server_default='0')

class Task(Base, SoftDelete):
    __tablename__ = 'agile_task'

    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey(Project.id), nullable=False)
    user_story_id = Column(ForeignKey(UserStory.id), nullable=False)
    name = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, server_default='0')
