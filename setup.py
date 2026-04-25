from setuptools import setup, find_packages

setup(
    name="csv-compare-util",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.0.0",
        "rapidfuzz>=3.0.0",
        "click>=8.0.0",
        "jinja2>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "csv-compare=csv_compare.cli:main",
        ],
    },
)
