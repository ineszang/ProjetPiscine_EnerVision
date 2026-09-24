# Pourquoi : la CI (job compose d'infra.yml) démarre le vrai conteneur Garage et joue ces tests avec
# boto3, sans venv projet. Ils prouvent que le S3 accepte des écritures, les rend intactes, supprime
# vraiment, et que SSE-C refuse une lecture sans clé (ADR 0019, 0020) - test_smoke.py

import base64
import os
import uuid

import boto3
import pytest
from botocore.exceptions import ClientError

BUCKET = os.environ.get("GARAGE_BUCKET", "enervision-archives")
ENDPOINT_URL = os.environ.get(
    "GARAGE_ENDPOINT_URL", f"http://127.0.0.1:{os.environ.get('GARAGE_S3_PORT', '3900')}"
)
SSE_KEY = base64.b64decode(os.environ["GARAGE_SSE_KEY"])
SSE = {"SSECustomerAlgorithm": "AES256", "SSECustomerKey": SSE_KEY}


@pytest.fixture
def client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=os.environ["GARAGE_ACCESS_KEY"],
        aws_secret_access_key=os.environ["GARAGE_SECRET_KEY"],
        region_name="garage",
    )


def test_default_bucket_exists(client):
    noms = [bucket["Name"] for bucket in client.list_buckets()["Buckets"]]

    assert BUCKET in noms


def test_upload_and_download_roundtrip(client):
    cle = f"fumee/{uuid.uuid4()}.txt"
    contenu = b"contenu de test EnerVision"

    client.put_object(Bucket=BUCKET, Key=cle, Body=contenu)
    recupere = client.get_object(Bucket=BUCKET, Key=cle)["Body"].read()
    client.delete_object(Bucket=BUCKET, Key=cle)

    assert recupere == contenu


def test_deleted_object_is_really_gone(client):
    cle = f"fumee/suppression-{uuid.uuid4()}.txt"
    client.put_object(Bucket=BUCKET, Key=cle, Body=b"a supprimer")

    client.delete_object(Bucket=BUCKET, Key=cle)

    with pytest.raises(client.exceptions.NoSuchKey):
        client.get_object(Bucket=BUCKET, Key=cle)


def test_sse_c_object_is_unreadable_without_the_key(client):
    cle = f"fumee/chiffre-{uuid.uuid4()}.txt"
    contenu = b"archive chiffree"
    client.put_object(Bucket=BUCKET, Key=cle, Body=contenu, **SSE)

    with pytest.raises(ClientError) as erreur:
        client.get_object(Bucket=BUCKET, Key=cle)
    dechiffre = client.get_object(Bucket=BUCKET, Key=cle, **SSE)["Body"].read()
    client.delete_object(Bucket=BUCKET, Key=cle)

    assert erreur.value.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert dechiffre == contenu
