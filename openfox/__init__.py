try:
    from ._version import version as __version__  # pyright: ignore[reportMissingImports]
except ImportError:
    try:
        from importlib.metadata import version as _pkg_version

        __version__ = _pkg_version("openfox")
    except Exception:
        __version__ = "0+unknown"
