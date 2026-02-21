"""Setuptools build entry for the native algorithms extension."""

import os

from setuptools import Extension, setup

extra_compile_args = ["/O2"] if os.name == "nt" else ["-O3"]

setup(
    ext_modules=[
        Extension(
            "qqmusic_api.algorithms._core",
            sources=["qqmusic_api/algorithms/_core.c"],
            extra_compile_args=extra_compile_args,
        )
    ]
)
