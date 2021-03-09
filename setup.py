from setuptools import setup

setup(
    install_requires=[
        'discord.py>=1.6.0',
        'requests'
    ],
    extras_require={
        'tests': [
            'pytest',
            'pytest-timeout',
            'pytest-asyncio'
        ]
    }
)
