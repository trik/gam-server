import pytest
import falcon
from falcon import testing

from gam.tests.fixtures import client

# an unathorized request on this endpoint should still deliver 200
def test_base_resource_get(client):
    response = client.simulate_get('/open_users',
    )
    assert response.status == falcon.HTTP_200