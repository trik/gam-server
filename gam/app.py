import falcon
from falcors import CORS

from agile.resources import (
    EpicResource,
    TaskResource,
    UserStoryResource,
)
from projects.resources import (
    ProjectResource,
)
from sync.resources import SyncResource
from users.resources import (
    LoginResource,
    LogoutResource,
    MeResource,
    RefreshTokenResource,
    RolesResource,
    UsersResource,
    UserSettingResource,
)
from .middleware import auth_middleware
from .resources import ModelResource
from .settings import DEBUG, I18N_ASSETS_PATH

def create_app():
    cors = CORS(allow_all_origins=True, allow_all_headers=True, allow_all_methods=True)
    # cors = CORS(allow_all_origins=True, allow_origins_list=ALLOWED_ORIGINS, allow_all_headers=True, allow_all_methods=True)
    app = falcon.API(middleware=[cors.middleware, auth_middleware])
    
    app.add_route('/auth/login', LoginResource())
    app.add_route('/auth/logout', LogoutResource())
    app.add_route('/auth/refresh_token', RefreshTokenResource())
    app.add_route('/users/me', MeResource())
    
    ModelResource.register_endpoints('/epics', app, EpicResource())
    ModelResource.register_endpoints('/projects', app, ProjectResource())
    ModelResource.register_endpoints('/roles', app, RolesResource())
    ModelResource.register_endpoints('/tasks', app, TaskResource())
    ModelResource.register_endpoints('/users', app, UsersResource())
    ModelResource.register_endpoints('/user_settings', app, UserSettingResource())
    ModelResource.register_endpoints('/user_stories', app, UserStoryResource())

    sync_resource = SyncResource()
    app.add_route('/sync/changes', sync_resource, suffix='changes')
    app.add_route('/sync/doc/{obj_id}', sync_resource, suffix='doc')
    app.add_route('/sync/docs', sync_resource, suffix='docs')

    if DEBUG:
        app.add_static_route('/assets/i18n', I18N_ASSETS_PATH)

    return app

def get_app():
    return create_app()
