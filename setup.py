from setuptools import setup, find_packages

setup(
    name="grip-sdk",
    version="0.3.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "google_ai_search": ["templates/*.html", "static/*"],
        "app": ["templates/*.html"],
    },
    entry_points={
        "console_scripts": [
            "grip=grip.cli:main",
            "grip-sdk=grip.cli:main",
            "google-ai-search=grip.cli:main",
        ],
    },
)
