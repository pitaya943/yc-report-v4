"""The alternative that was weighed: let the object store expire the link.

Asks a local moto server for a presigned GET URL that lives 2 seconds, fetches
it at once, waits 4 real seconds and fetches it again. Prints what happened.
Run:  .venv/bin/python experiments/presigned_on_moto.py
"""
import socket
import time
import urllib.error
import urllib.request

import boto3
from moto.server import ThreadedMotoServer


def fetch(url: str) -> str:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url) as response:
            return f"HTTP {response.status}, {len(response.read())} bytes"
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}"


with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
server = ThreadedMotoServer(ip_address="127.0.0.1", port=port, verbose=False)
server.start()
try:
    client = boto3.client("s3", endpoint_url=f"http://127.0.0.1:{port}",
                          region_name="us-east-1", aws_access_key_id="test",
                          aws_secret_access_key="test")
    client.create_bucket(Bucket="spike")
    client.put_object(Bucket="spike", Key="receipt", Body=b"%PDF-1.7 spike")
    url = client.generate_presigned_url(
        "get_object", Params={"Bucket": "spike", "Key": "receipt"}, ExpiresIn=2)
    print("presigned URL lifetime: 2 seconds")
    print("fetched at once:        ", fetch(url))
    time.sleep(4)
    print("fetched 4 seconds later:", fetch(url))
finally:
    server.stop()
