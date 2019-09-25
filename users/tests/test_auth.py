import jwt
import time
import simplejson as json
import pytest
import falcon

from falcon import testing
from falcon_auth import JWTAuthBackend

from gam import app
from gam import middleware
from gam import settings
from gam.database import scoped_session
from users.hasher import encode_password
from users.models import RefreshToken, User
from users.resources import LoginResource
from users.schemas import TokenPayloadSchema
from users.utils import get_authenticated_user

from gam.tests.fixtures import (
    client, language,  login, token, john_snow,
    role_super_admin, role_country_admin, role_admin
)


# -------- Login ----------------------
# an empty post request should return 400
def test_empty_login_post(client):
    response = client.simulate_post('/auth/login')
    assert response.status == falcon.HTTP_400

# an incorrectly filled post request should return 400
def test_incorrectly_filled_login_post(client):
    response = client.simulate_post('/auth/login', params={'foo':'bar'})
    assert response.status == falcon.HTTP_400

# wrong credentials post request should be notified with 400
def test_wrong_credentials_login_post(client):
    response = client.simulate_post('/auth/login', params={
        'username':'dr_doom',
        'password':'xxxxxx'
    })
    assert response.status == falcon.HTTP_400

# right credentials should return status 200
def test_right_credentials_login_post(client, john_snow):

    response = client.simulate_post('/auth/login', body=json.dumps({
        'username':john_snow.username,
        'password':'12345'
    }))
    assert response.status == falcon.HTTP_200


# -------- Logout ---------------------
# an empty post request should return 401 if the user is not logged
def test_empty_logout_unlogged_post(client):
    response = client.simulate_post('/auth/logout')
    assert response.status == falcon.HTTP_401

# an empty post request should return 200 if the user was already logged
# and the refresh token should be removed
def test_right_logout_logged_post(client, token):
    response = client.simulate_post(
        '/auth/logout',
        headers={
            'authorization': 'jwt %s' % token
        }
    )
    assert response.status == falcon.HTTP_200


# -------- Refresh Token --------------
# an empty post request should return 401
def test_empty_refresh_token_post(client):
    response = client.simulate_post('/auth/refresh_token')
    assert response.status == falcon.HTTP_401

# an incorrectly filled post request should return 400
def test_incorrectly_filled_refresh_token_post(client, token):
    response = client.simulate_post(
        '/auth/refresh_token',
        headers={
            'authorization': 'jwt %s' % token
        },
        body=json.dumps({
            'refresh_token':'xxx'
        })
    )
    assert response.status == falcon.HTTP_400
    
# right refresh token should return status 200
def test_right_refresh_token_post(client, login):
    response = client.simulate_post(
        '/auth/refresh_token',
        headers={
            'authorization': 'jwt %s' % login['token']
        },
        body=json.dumps({
            'refresh_token':login['refresh_token']
        })
    )
    assert response.status == falcon.HTTP_200

# a correct request with an expired token should give a new token 
# and return 200
def test_right_expired_refresh_token_post(client, john_snow):
    auth_backend = JWTAuthBackend(get_authenticated_user, settings.SECRET_KEY, expiration_delta=0)
    uid = john_snow.id
    with scoped_session() as session:
        refresh_token = session.query(RefreshToken).filter(RefreshToken.user_id == uid).first().token
        token = auth_backend.get_auth_token(TokenPayloadSchema().dump(john_snow).data)
    decoded = jwt.decode(token, key=settings.SECRET_KEY, algorithms='HS256')

    assert decoded is not None and 'exp' in decoded
    time.sleep(1)
    assert decoded['exp'] < int(time.time())

    response = client.simulate_post(
        '/auth/refresh_token',
        headers={
            'authorization': 'jwt %s' % token
        },
        body=json.dumps({
            'refresh_token': refresh_token
        })
    )
    assert response.status == falcon.HTTP_200
    assert response.json['token'] != token
