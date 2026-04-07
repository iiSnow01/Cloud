import os
import sys


def code_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def runtime_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return code_root()


def runtime_path(*parts: str) -> str:
    return os.path.join(runtime_root(), *parts)
