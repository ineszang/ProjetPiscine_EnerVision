"""
Tests de fumée pour Garage — vérifie que le cluster local accepte
vraiment des écritures et les rend intactes, pas juste qu'il démarre.
"""
import os
import uuid

import boto3
import pytest

ENDPOINT_URL = "http://127.0.0.1:3900"
ACCESS_KEY = os.environ["GARAGE_ACCESS_KEY"]
SECRET_KEY = os.environ["GARAGE_SECRET_KEY"]
BUCKET = "enervision-raw-test"


@pytest.fixture
def client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="garage",
    )


def test_bucket_exists(client):
    response = client.list_buckets()
    noms = [b["Name"] for b in response["Buckets"]]
    assert BUCKET in noms


def test_upload_and_download_roundtrip(client):
    cle = f"test-{uuid.uuid4()}.txt"
    contenu = b"contenu de test EnerVision"

    client.put_object(Bucket=BUCKET, Key=cle, Body=contenu)

    reponse = client.get_object(Bucket=BUCKET, Key=cle)
    recupere = reponse["Body"].read()

    assert recupere == contenu

    client.delete_object(Bucket=BUCKET, Key=cle)


def test_deleted_object_is_really_gone(client):
    cle = f"test-suppression-{uuid.uuid4()}.txt"
    client.put_object(Bucket=BUCKET, Key=cle, Body=b"a supprimer")

    client.delete_object(Bucket=BUCKET, Key=cle)

    with pytest.raises(client.exceptions.NoSuchKey):
        client.get_object(Bucket=BUCKET, Key=cle)
