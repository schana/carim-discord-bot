from setuptools import setup

setup(
    install_requires=[
        'discord.py>=1.3.4,<1.4.0a0',
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
