from datetime import datetime

from marshmallow.schema import Schema
from marshmallow.fields import Email, Function, Integer, Nested
from marshmallow_sqlalchemy import ModelSchema

from gam.settings import ONLINE_TIME_SPAN
from sync.decorators import sync_model
from .models import Role, User, UserRole, UserSetting
from .permissions import SelfFilter, SuperAdminWriteFilter, UsersFilter

class UserRoleSchema(ModelSchema):
    class Meta:
        model = UserRole
        fields = (
            'user_id', 'role_id', 'extra',
        )

@sync_model(permissions=(UsersFilter, ))
class UserSchema(ModelSchema):
    email = Email()
    roles = Nested(UserRoleSchema, attribute='role_assoc', many=True, exclude=('user_id', ))

    class Meta:
        model = User
        fields = (
           'id',
           'username', 'first_name', 'last_name', 'email', 'roles',
           'acted_id', 'language_id', 'date_joined', 'is_active',
        )

class UserCreateSchema(ModelSchema):
    email = Email()
    roles = Nested(UserRoleSchema, attribute='role_assoc', many=True, exclude=('user_id', ))

    class Meta:
        model = User
        fields = (
           'username', 'first_name', 'last_name', 'email', 'password',
           'acted_id', 'language_id', 'roles', 'date_joined', 'is_active',
        )

class TokenPayloadSchema(ModelSchema):
    user_id = Function(lambda obj: obj.id)
    scopes = Function(lambda _: ['user', 'admin'])

    class Meta:
        model = User
        fields = (
            'user_id', 'username', 'scopes'
        )

@sync_model(permissions=(SuperAdminWriteFilter, ))
class RoleSchema(ModelSchema):
    class Meta:
        model = Role
        fields = (
            'id', 'name', 'label',
        )

@sync_model(permissions=(SelfFilter, ))
class UserSettingSchema(ModelSchema):
    class Meta:
        model = UserSetting
        fields = (
            'id', 'user_id', 'settings',
        )

class OnlineUserSchema(Schema):
    id = Integer()
    name = Function(lambda obj: '{} {}'.format(obj.first_name, obj.last_name) \
        if obj.first_name is not None and obj.last_name is not None else obj.username)
    online = Function(lambda obj: obj.ping_time is not None \
        and (datetime.now() - obj.ping_time) < ONLINE_TIME_SPAN)
