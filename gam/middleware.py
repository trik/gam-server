import falcon
import jwt

from jwt import InvalidTokenError

from falcon_auth import FalconAuthMiddleware, JWTAuthBackend

from users.utils import get_authenticated_user
from gam.settings import JWT_EXPIRATION_DELTA, SECRET_KEY


class ExpiredJWTAuthBackend(JWTAuthBackend):
    def _decode_jwt_token(self, req):
        # Decodes the jwt token into a payload
        auth_header = req.get_header('Authorization')
        token = self.parse_auth_token_from_request(auth_header=auth_header)

        options = dict(('verify_' + claim, True) for claim in self.verify_claims)

        options.update(
            dict(('require_' + claim, True) for claim in self.required_claims)
        )
        options.update({'verify_exp': False})

        try:

            payload = jwt.decode(jwt=token, key=self.secret_key,
                                 options=options,
                                 algorithms=[self.algorithm],
                                 issuer=self.issuer,
                                 audience=self.audience,
                                 leeway=self.leeway)
        except InvalidTokenError as ex:
            raise falcon.HTTPUnauthorized(
                title='401 Unauthorized',
                description=str(ex),
                challenges=None)

        return payload


auth_backend = JWTAuthBackend(get_authenticated_user, SECRET_KEY, expiration_delta=JWT_EXPIRATION_DELTA)
auth_expired_backend = ExpiredJWTAuthBackend(get_authenticated_user, SECRET_KEY,
    expiration_delta=JWT_EXPIRATION_DELTA,
    verify_claims=['signature', 'nbf', 'iat'])
auth_middleware = FalconAuthMiddleware(auth_backend, exempt_routes=['/open_users'])
