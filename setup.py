from pathlib import Path

from setuptools import setup, find_packages


def engine_version() -> str:
    """The engine's version, written once in `taktik/__init__.py`.

    Read as text: importing the package would need its dependencies, and creates its log folder.
    """
    init = Path(__file__).resolve().parent / "taktik" / "__init__.py"
    for line in init.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError(f"no __version__ in {init}")


def runtime_requirements() -> list:
    """What the engine needs to run, read from `requirements.txt`: the one list of them.

    `pip install -r requirements.txt` and `pip install .` install the same thing. A line that is
    not a requirement (an option such as `-r`) stops the build rather than being skipped.
    """
    path = Path(__file__).resolve().parent / "requirements.txt"
    requirements = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-"):
            raise RuntimeError(f"{path.name}: '{line}' is not a requirement setup.py can read")
        requirements.append(line)
    return requirements


setup(
    name="taktik-bot",
    version=engine_version(),
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=runtime_requirements(),
    entry_points={
        "console_scripts": [
            "taktik=taktik.cli.main:cli",
            # No `taktik-instagram`: it pointed at `taktik.cli.main:instagram`, which does not
            # exist, so the entry point failed at import for anyone who installed the package.
            # Instagram is reached as `taktik automation ...` / `taktik management ...`.
            "taktik-tiktok=taktik.cli.main:tiktok"
        ],
    },
    author="Taktik",
    author_email="contact@taktik-bot.com",
    description="Instagram, TikTok, YouTube, Threads and Gmail automation on real Android devices "
                "(uiautomator2, ADB), from the command line or the TAKTIK desktop app",
    long_description=open("README.md", encoding='utf-8').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/masterFuf/taktik-bot",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
    ],
)
