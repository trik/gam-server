from sqlalchemy import (
    Boolean, cast, Column, DateTime, ForeignKey, func, Integer, JSON, String, text
)
from sqlalchemy.orm import backref, relationship
from sqlalchemy.dialects.postgresql import JSONB

from gam.database import Base, Fixed, SoftDelete
from .hasher import verify_password

class Permission(Base, SoftDelete):
    __tablename__ = 'users_permission'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)

class Role(Base, Fixed, SoftDelete):
    __tablename__ = 'users_role'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    label = Column(String(50), nullable=False)
    fixed = Column(Boolean(), server_default='FALSE', nullable=False)

class User(Base, Fixed, SoftDelete):
    __tablename__ = 'users_user'

    id = Column(Integer, primary_key=True)
    username = Column(String(150), unique=True, nullable=False)
    password = Column(String(128), nullable=False)
    first_name = Column(String(30), nullable=True)
    last_name = Column(String(150), nullable=True)
    email = Column(String(254), nullable=True)
    date_joined = Column(DateTime, server_default=func.now(), nullable=False)
    fixed = Column(Boolean(), server_default='FALSE', nullable=False)
    is_active = Column(Boolean(), server_default='TRUE', nullable=False)
    roles = relationship('Role', secondary='users_user_role')

    def verify_password(self, password):
        return verify_password(password, self.password)
    
    def user_id(self):
        return self.id
    
    def scopes(self):
        return ['user', 'admin']

    def __repr__(self):
        return '<User(username="{}")>'.format(self.username)

class UserSetting(Base, SoftDelete):
    __tablename__ = 'users_user_setting'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey(User.id), unique=True, nullable=False)
    settings = Column(JSON, nullable=False, default=JSON.NULL)

class RefreshToken(Base):
    __tablename__ = 'users_refreshtoken'
    user_id = Column(Integer, ForeignKey(User.id, ondelete='CASCADE'), primary_key=True)
    token = Column(String(50), server_default=func.md5(cast(func.random(), String)), nullable=False)

    def __repr__(self):
        return '<RefreshToken(user_id="{}")>'.format(self.user_id)

class UserRole(Base):
    __tablename__ = 'users_user_role'

    user_id = Column(Integer, ForeignKey(User.id), nullable=False, primary_key=True)
    role_id = Column(Integer, ForeignKey(Role.id), nullable=False, primary_key=True)
    extra = Column('extra', JSONB, nullable=False, server_default=text('{}'))
    user = relationship(User, backref=backref("role_assoc"))
    role = relationship(Role, backref=backref("user_assoc"))
