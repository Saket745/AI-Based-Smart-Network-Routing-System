import tempfile
from pathlib import Path
import pytest
from nroute.utils.loader import load_custom_class

def test_load_custom_class_security() -> None:
    """Test security restrictions in load_custom_class."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test_module.py"
        file_path.write_text("class TestClass: pass")

        import_str = f"{file_path}:TestClass"

        # Should fail by default
        with pytest.raises(PermissionError, match="restricted for security reasons"):
            load_custom_class(import_str)

        # Should succeed with allow_unsafe=True
        cls = load_custom_class(import_str, allow_unsafe=True)
        assert cls.__name__ == "TestClass"

def test_load_custom_class_module_still_works() -> None:
    """Test that loading from standard modules still works without allow_unsafe."""
    # os:Path is not a class, but we can use something else
    # actually load_custom_class checks isinstance(cls, type)

    # Let's use a class from a standard library
    import_str = "json.decoder:JSONDecoder"
    cls = load_custom_class(import_str)
    assert cls.__name__ == "JSONDecoder"
