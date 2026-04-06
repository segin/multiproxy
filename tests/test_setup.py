def test_app_import():
    try:
        from app.main import app
        assert app is not None
        assert app.title == "MultiProxy"
    except ImportError:
        assert False, "app.main could not be imported"