import importlib


def test_streamlit_app_imports_successfully():
    module = importlib.import_module("app.streamlit_app")

    assert hasattr(module, "main")
