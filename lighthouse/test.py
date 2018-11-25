import json
import os

import pytest
from starlette.testclient import TestClient

from app import app
from model import init_db, inject_test_data

FILE_NAME = os.path.join(
    os.path.split(__file__)[0], "test_data/jenkins_env_sample.json"
)
TAG = "jenkins-Clipper-PRB-1672"


@pytest.fixture(scope="session")
def client():
    client_app = TestClient(app)
    init_db(debug=True)
    inject_test_data(FILE_NAME, TAG)
    return client_app


def test_build(client):
    env = json.load(open(FILE_NAME))
    tag = "test_build_tag"
    env["BUILD_TAG"] = tag

    # create build
    resp = client.post(f"/api/build", json=env)
    assert resp.status_code == 200

    # retrieve build
    resp = client.get(f"/api/build/{tag}")
    assert resp.status_code == 200
    assert set(resp.json().keys()) - set(env.keys()) == set(["make_file"])

    # create checkpoints
    target_name = "build_py36rpc"
    resp = client.post(f"/api/checkpoint/{tag}/{target_name}/start")
    assert resp.status_code == 200, resp.content
    resp = client.post(f"/api/checkpoint/{tag}/{target_name}/finish?exit_code=1")
    assert resp.status_code == 200, resp.content

    # get checkpoints
    resp = client.get(f"/api/checkpoint/{tag}/*")
    assert len(resp.json()) == 2, resp.content

    resp = client.get(f"/api/checkpoint/*/{target_name}")
    assert len(resp.json()) == 4, resp.content
