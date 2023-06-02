#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst", encoding="utf-8") as history_file:
    history = history_file.read()

requirements = [
    "Click>=7.0",
    "pulp",
    "rich",
    "typing_extensions",
    "cloudmodel @ git+https://jentrialgo@github.com/jldiaz-uniovi/cloudmodel.git#egg=cloudmodel",
]

test_requirements = [
    "pytest>=3",
]

setup(
    author="Joaquín Entrialgo",
    author_email="joaquin@uniovi.es",
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
    ],
    description="Edge architecture optimizator",
    entry_points={
        "console_scripts": [
            "edarop=edarop.cli:main",
        ],
    },
    install_requires=requirements,
    license="MIT license",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="edarop",
    name="edarop",
    packages=find_packages(include=["edarop", "edarop.*"]),
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/jentrialgo/edarop",
    version="0.1.0",
    zip_safe=False,
)
