import os
import sys

try:
    import streamlit  # noqa: F401
except ImportError:

    class _StubSecrets:
        def get(self, chave, default=None):
            return os.environ.get(chave, default)

    class _FakeStreamlit:
        secrets = _StubSecrets()

    sys.modules["streamlit"] = _FakeStreamlit()
