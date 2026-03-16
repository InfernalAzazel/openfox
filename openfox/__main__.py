"""
将 openfox 作为模块运行的入口点: python -m openfox
"""

from openfox.cli.commands import app

if __name__ == "__main__":
    app()