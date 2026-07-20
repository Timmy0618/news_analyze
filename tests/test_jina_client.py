import os
from unittest import mock
from utils.jina_client import JinaClient


def test_default_model_is_v5():
    with mock.patch.dict(os.environ, {"JINA_API_KEY": "x"}, clear=False):
        os.environ.pop("JINA_MODEL", None)
        assert JinaClient().model == "jina-embeddings-v5-text-small"


def test_model_overridable_via_env():
    with mock.patch.dict(os.environ, {"JINA_API_KEY": "x", "JINA_MODEL": "jina-embeddings-v3"}):
        assert JinaClient().model == "jina-embeddings-v3"
