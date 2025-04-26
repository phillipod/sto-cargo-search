from setuptools import setup, find_packages

setup(
    name='sto-cargo-search',
    version='1.0.0',
    description='Search Star Trek Online CargoExport JSON data',
    author='Phillip O\'Donnell',
    author_email='phillip.odonnell@gmail.com',
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    install_requires=[
        'requests',
        'prettytable',
        'pyparsing',
    ],
    entry_points={
        'console_scripts': [
            'sto-cargo-search=sto_cargo_search.cli:main',
        ],
    },
    python_requires='>=3.7',
)
