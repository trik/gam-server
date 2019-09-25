from gam.database import scoped_session
from .hasher import verify_password
from .models import User, UserRole

def get_authenticated_user(payload):
    try:
        user_id = payload['user']['user_id']
        with scoped_session() as session:
            user = session.query(User).filter(
                User.id == user_id
            ).one_or_none()
            session.expunge_all()
        return user
    except KeyError:
        return None

def authenticate_user(username, password):
    with scoped_session() as session:
        user = session.query(User).filter(
            User.username == username,
            User.is_active.is_(True),
            User.deleted.is_(False)
        ).one_or_none()
        session.expunge_all()
    if user is not None and not verify_password(password, user.password):
        return None
    return user

def get_user_roles_map(uid, extended=False):
    roles = {}
    with scoped_session() as session:
        q = session.query(UserRole).filter(UserRole.user_id == uid)
        for role in q:
            extra = {**role.extra}
            roles[role.role_id] = extra
    return roles
