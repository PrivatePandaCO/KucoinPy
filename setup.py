from distutils.core import setup

setup(
    name="KucoinPy",
    version="0.0.2",
    description="Probably the fastest kucoin API wrapper in python",
    author="Parth Mittal",
    author_email="parth@privatepanda.co",
    url="https://www.github.com/PrivatePandaCO/KucoinPy",
    license="GNU GENERAL PUBLIC LICENSE Version 2",
    packages=["KucoinPy"],
    install_requires=["orjson", "requests", "pyloggor"],
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    project_urls={
        "Documentation": "https://github.com/PrivatePandaCO/KucoinPy/blob/master/README.md",
        "Github": "https://github.com/PrivatePandaCO/KucoinPy",
        "Changelog": "https://github.com/PrivatePandaCO/KucoinPy/blob/master/changelog.md"
    },
)
