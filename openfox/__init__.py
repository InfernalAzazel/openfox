try:
    from ._version import version as __version__  # pyright: ignore[reportMissingImports]
except ImportError:
    try:
        from importlib.metadata import version as _pkg_version

        __version__ = _pkg_version("openfox")
    except Exception:
        try:
            from pathlib import Path

            from setuptools_scm import get_version as _scm_get_version

            _repo_root = Path(__file__).resolve().parent.parent
            __version__ = _scm_get_version(root=str(_repo_root), relative_to=__file__)
        except Exception:
            __version__ = "0+unknown"
