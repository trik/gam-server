from datetime import datetime

import ujson as json

from falcon import HTTP_BAD_REQUEST, HTTP_OK, MEDIA_JSON, Request, Response

from sqlalchemy import false

from gam.database import scoped_session
from gam.middleware import auth_backend, auth_expired_backend
from gam.resources import ModelResource
from .hasher import make_password
from .models import RefreshToken, Role, User, UserRole, UserSetting
from .permissions import SuperAdminWriteFilter, UsersFilter
from .schemas import (
    OnlineUserSchema, RoleSchema, TokenPayloadSchema, UserCreateSchema, UserSchema, UserSettingSchema,
)
from .utils import authenticate_user


class LoginResource:
    auth = {
        'exempt_methods': ['OPTIONS', 'POST']
    }

    def on_post(self, req: Request, resp: Response):
        """Unprotected user login endpoint.
        ---
        post:
            description: Logs an existing user returning valid tokens
            consumes: ["json"]
            parameters:
            -   in: body
                name: credentials
                description: The username and password chosen during the registration
                schema: {}
                required: true
            responses:
                200:
                    description: Tokens needed for authorization and refresh token
                    schema: TokenPayloadSchema
                401:
                    description: Submitted invalid credentials
        """
        resp.content_type = MEDIA_JSON
        try:
            params = json.loads(req.stream.read(req.content_length or 0))
            username = params['username']
            password = params['password']
        except (KeyError, TypeError, ValueError):
            resp.body = '{"message": "Please provide username and password"}'
            resp.status = HTTP_BAD_REQUEST
            return
        user = authenticate_user(username, password)
        if user is None:
            resp.body = '{"message": "Invalid credentials"}'
            resp.status = HTTP_BAD_REQUEST
            return
        payload = TokenPayloadSchema().dump(user)
        payload['token'] = auth_backend.get_auth_token(payload)
        with scoped_session() as session:
            rt = session.query(RefreshToken).filter(
                RefreshToken.user_id == payload['user_id']
            ).first()
            if rt is None:
                rt = RefreshToken(user_id=payload['user_id'])
                session.add(rt)
                session.commit()
            refresh_token = rt.token
            user_instance = session.query(User).filter(User.id == user.id).first()
            payload['user'] = UserSchema().dump(user_instance)
        payload['refresh_token'] = refresh_token
        resp.body = json.dumps(payload)
        resp.status = HTTP_OK

class LogoutResource:
    def on_post(self, req: Request, resp: Response):
        """User logout endpoint.
        ---
        post:
            description: Logs out an already logged user
            responses:
                200:
                    description: Logs out the user deleting the refresh token
                401:
                    description: Fails on unauthorized (tokenless) request
        """
        user = req.context['user']
        with scoped_session() as session:
            rt = session.query(RefreshToken).filter(
                RefreshToken.user_id == user.id
            ).first()
            if rt is not None:
                session.delete(rt)
        resp.status = HTTP_OK

class RefreshTokenResource:
    auth = {
        'backend': auth_expired_backend
    }

    def on_post(self, req: Request, resp: Response):
        """Refresh token endpoint for getting new auth tokens.
        ---
        post:
            description: Returns a new token both on valid and expired submitted token
            consumes: ["json"]
            parameters:
            -   in: body
                name: refresh_token
                description: refresh token needed to access the endpoint
                required: true
            responses:
                200:
                    description: User info, and tokens needed for new requests
                401:
                    description: Submitted a tokenless request
                400:
                    description: Missing a valid refresh token
        """
        user = req.context['user']
        try:
            params = json.loads(req.stream.read(req.content_length or 0))
            refresh_token = params['refresh_token']
        except (KeyError, TypeError, ValueError):
            resp.body = '{"message": "Please provide a refresh token"}'
            resp.status = HTTP_BAD_REQUEST
            return
        with scoped_session() as session:
            rt = session.query(RefreshToken).filter(
                RefreshToken.user_id == user.id,
                RefreshToken.token == refresh_token
            ).first()
            if rt is None:
                resp.body = '{"message": "Invalid refresh token"}'
                resp.status = HTTP_BAD_REQUEST
                return
        payload = TokenPayloadSchema().dump(user).data
        payload['token'] = auth_backend.get_auth_token(payload)
        payload['refresh_token'] = refresh_token
        resp.body = json.dumps(payload)
        resp.status = HTTP_OK

class UsersResource(ModelResource):
    model_class = User
    schema_class = UserSchema
    schema_classes = {
        'post': UserCreateSchema,
        'put': UserSchema,
        'patch': UserSchema,
        'get': UserSchema,
    }
    permissions = (UsersFilter, )

    def __init__(self):
        super().__init__()
        self.__roles = None

    def _process_create_data(self, data):
        if 'password' in data:
            data['password'] = make_password(data['password'])
        if 'roles' in data:
            self.__roles = data['roles']
            del data['roles']

    def _process_update_data(self, data, input_data):
        if 'password' in input_data and input_data['password'] is not None:
            input_data['password'] = make_password(input_data['password'])
        else:
            input_data['password'] = data.password
        if 'roles' in input_data:
            self.__roles = input_data['roles']
            del input_data['roles']
    
    def _post_create(self, session, instance):
        self.__update_roles(session, instance)
    
    def _post_update(self, session, instance):
        self.__update_roles(session, instance)
    
    def __update_roles(self, session, instance):
        if self.__roles is None:
            return
        existing_user_roles = []
        for role in self.__roles:
            role_id = role['role_id'] or None if 'role_id' in role else None
            extra = role['extra'] or {} if 'extra' in role else {}
            user_role = session.query(UserRole).filter(
                UserRole.user_id == instance.id,
                UserRole.role_id == role['role_id']).first()
            if user_role is None:
                user_role = UserRole(
                    user_id=instance.id,
                    role_id=role_id,
                    extra=extra)
            else:
                user_role.extra = extra
            user_role.extra = extra
            session.add(user_role)
            session.commit()
            existing_user_roles.append(user_role.role_id)
        session.query(UserRole).filter(
            UserRole.user_id == instance.id,
            UserRole.role_id.notin_(existing_user_roles)).delete(synchronize_session=False)

class MeResource:
    def on_get(self, req: Request, resp: Response):
        user = req.context['user']
        with scoped_session() as session:
            instance = session.query(User).filter(
                User.id == user.id
            ).first()
            payload = UserSchema().dump(instance)
            resp.body = json.dumps(payload)
        resp.status = HTTP_OK

class RolesResource(ModelResource):
    model_class = Role
    schema_class = RoleSchema
    uri = '/roles'
    permissions = (SuperAdminWriteFilter, )

class UserSettingResource(ModelResource):
    model_class = UserSetting
    schema_class = UserSettingSchema
    uri = '/user_settings'
