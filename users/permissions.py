from sqlalchemy import and_, cast, or_
from sqlalchemy.dialects.postgresql import JSONB

from gam.database import scoped_session
from .models import User, UserRole
from .roles import (
    ROLE_ADMIN, ROLE_SUPER_ADMIN
)

class SuperAdminWriteFilter:
    @classmethod
    def apply_filter(cls, ctx, queryset):
        method = ctx['method']
        roles = ctx['roles']

        if method in ('get', 'list', ):
            return queryset
        if ROLE_SUPER_ADMIN not in roles:
            return queryset.filter(False)
        return queryset
    
    @classmethod
    def can_create(cls, ctx, _new_obj):
        roles = ctx['roles']

        return ROLE_SUPER_ADMIN in roles
    
    @classmethod
    def can_read_change(cls, _ctx, _itm):
        return True

class CountryAdminWriteFilter:
    @classmethod
    def apply_filter(cls, ctx, queryset):
        method = ctx['method']
        roles = ctx['roles']

        if method in ('get', 'list', ):
            return queryset
        if ROLE_COUNTRY_ADMIN not in roles:
            return queryset.filter(False)
        return queryset
    
    @classmethod
    def can_create(cls, ctx, _new_obj):
        roles = ctx['roles']

        return ROLE_COUNTRY_ADMIN in roles
    
    @classmethod
    def can_read_change(cls, _ctx, _itm):
        return True

class SelfFilter:
    @classmethod
    def apply_filter(cls, ctx, queryset):
        model_cls = ctx['model']
        user = ctx['user']
        if hasattr(model_cls, 'user_id'):
            return queryset.filter(model_cls.user_id == user.id)
        return queryset.filter(False)
    
    @classmethod
    def can_create(cls, ctx, new_obj):
        user = ctx['user']
        return 'user_id' in new_obj and new_obj['user_id'] == user.id
    
    @classmethod
    def can_read_change(cls, ctx, itm):
        user = ctx['user']
        return 'user_id' in itm and itm['user_id'] == user.id

class UsersFilter:
    @classmethod
    def apply_filter(cls, ctx, queryset):
        method = ctx['method']
        roles = ctx['roles']

        if method in ('get', 'list', ):
            return queryset
        
        filters = []
        
        filters.append(User.id == ctx['user'].id)
        filters_num = len(filters)
        if filters_num == 0:
            return queryset.filter(False)
        return queryset.filter(or_(*filters))

    @classmethod
    def __can_create_country_admin(cls, roles):
        return ROLE_SUPER_ADMIN in roles

    @classmethod
    def __can_create_admin(cls, roles, user_roles):
        if ROLE_COUNTRY_ADMIN in roles and 'countries' in roles[ROLE_COUNTRY_ADMIN]:
            ca_countries = roles[ROLE_COUNTRY_ADMIN]['countries']
            user_countries = user_roles[ROLE_ADMIN]['countries'] if 'countries' in user_roles[ROLE_ADMIN] else []
            return ca_countries == user_countries
        return False
    
    @classmethod
    def __get_admin_projects(cls, user_roles, user_roles_ids):
        admin_roles = (ROLE_ADMIN, ROLE_COUNTRY_ADMIN, ROLE_SUPER_ADMIN, )
        user_projects = []
        for urid in user_roles_ids:
            if urid in admin_roles:
                return False
            if 'projects' not in user_roles[urid]:
                return False
            projects = user_roles[urid]['projects']
            projects_num = len(projects)
            if projects_num == 0:
                return False
            for project in projects:
                if project not in user_projects:
                    user_projects.append(user_projects)
        return user_projects
    
    @classmethod
    def __can_create_mobile_roles(cls, roles, user_roles, user_roles_ids):
        if ROLE_ADMIN not in roles or 'countries' not in roles[ROLE_ADMIN]:
            return False
        countries = roles[ROLE_ADMIN]['countries']
        countries_num = len(countries)
        if countries_num == 0:
            return False
        
        user_projects = cls.__get_admin_projects(user_roles, user_roles_ids)
        user_projects_num = len(user_projects)
        if user_projects_num == 0:
            return False
        
        with scoped_session() as session:
            for c in session.query(Project.country_id).filter(Project.id.in_(user_projects)):
                if c[0] not in countries:
                    return False
        return True
    
    @classmethod
    def can_create(cls, ctx, new_obj):
        roles = ctx['roles']

        user_roles = {}
        if 'roles' in new_obj:
            for role in new_obj['roles']:
                user_roles[role['role_id']] = role['extra'] if 'extra' in role else {}
        user_roles_ids = [k for k in user_roles]
        if user_roles_ids == [ROLE_ADMIN]:
            return cls.__can_create_admin(roles, user_roles)
        return cls.__can_create_mobile_roles(roles, user_roles, user_roles_ids)
    
    @classmethod
    def __super_admin_can_read_change(cls, user_roles):
        for user_role in user_roles:
            if user_role.role_id == ROLE_COUNTRY_ADMIN:
                return True
        return False
    
    @classmethod
    def __country_admin_can_read_change(cls, roles, user_roles):
        countries = roles[ROLE_COUNTRY_ADMIN]['countries']
        countries_num = len(countries)
        if countries_num > 0:
            for user_role in user_roles:
                if user_role.role_id == ROLE_ADMIN:
                    user_countries = user_role.extra['countries'] \
                        if 'countries' in user_role.extra else []
                    for uc in user_countries:
                        if uc in countries:
                            return True
        return False
    
    @classmethod
    def __admin_can_read_change(cls, roles, user_roles):
        countries = roles[ROLE_ADMIN]['countries']
        countries_num = len(countries)
        projects = roles[ROLE_ADMIN]['projects']
        projects_num = len(projects)
        if countries_num > 0 or projects_num > 0:
            for user_role in user_roles:
                if countries_num > 0 and user_role.role_id == ROLE_OFFICER:
                    user_countries = user_role.extra['countries'] \
                        if 'countries' in user_role.extra else []
                    for uc in user_countries:
                        if uc in countries:
                            return True
                if projects_num > 0 and user_role.role_id in MOBILE_ROLES:
                    user_projects = user_role.extra['projects'] \
                        if 'projects' in user_role.extra else []
                    for up in user_projects:
                        if up in projects:
                            return True
        return False
    
    @classmethod
    def can_read_change(cls, ctx, itm):
        roles = ctx['roles']
        user = ctx['user']

        if itm['object_id'] == user.id:
            return True
        
        with scoped_session() as session:
            user_roles = session.query(UserRole).filter(UserRole.user_id == itm['object_id']).all()
        
            if ROLE_SUPER_ADMIN in roles and cls.__super_admin_can_read_change(user_roles):
                return True
            if (
                ROLE_COUNTRY_ADMIN in roles
                and 'countries' in roles[ROLE_COUNTRY_ADMIN]
                and cls.__country_admin_can_read_change(roles, user_roles)
            ):
                return True
            if ROLE_ADMIN in roles and 'countries' in roles[ROLE_ADMIN] and cls.__admin_can_read_change(roles, user_roles):
                return True
        return False
