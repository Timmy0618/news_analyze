import os
from unittest import mock
from utils.jina_client import JinaClient


def test_defaults_point_at_local_server():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EMBED_URL", None)
        os.environ.pop("EMBED_MODEL", None)
        c = JinaClient()
        assert c.api_url == "http://localhost:8003/v1/embeddings"
        assert c.model == "qwen3-embed"


def test_overridable_via_env():
    with mock.patch.dict(os.environ, {"EMBED_URL": "http://h:9/v1/", "EMBED_MODEL": "m"}):
        c = JinaClient()
        assert c.api_url == "http://h:9/v1/embeddings"
        assert c.model == "m"


def test_payload_has_no_jina_only_fields():
    # vLLM 會對 dimensions/task 直接回 400
    assert JinaClient()._payload(["a"]) == {"model": JinaClient().model, "input": ["a"]}
