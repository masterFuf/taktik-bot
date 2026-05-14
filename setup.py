from setuptools import setup, find_packages

setup(
    name="taktik-bot",
    version="1.1.6",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "rich>=10.0.0",
        "pure-python-adb>=0.3.0.dev0",  # Version de développement
        "uiautomator2>=2.16.0",
        "cryptography>=35.0.0",
        "pyyaml>=6.0",
        "requests>=2.27.0",
        "pillow>=9.0.0",
    ],
    entry_points={
        "console_scripts": [
            "taktik=taktik.cli.main:cli",
            "taktik-instagram=taktik.cli.main:instagram",
            "taktik-tiktok=taktik.cli.main:tiktok"
        ],
    },
    author="Taktik",
    author_email="contact@taktik-bot.com",
    description="Plateforme d'automatisation Instagram & TikTok",
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
