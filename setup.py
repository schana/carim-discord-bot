from setuptools import setup

setup(
    install_requires=[
        'discord.py>=1.3.2,<1.4.0a0'
    ],
    extras_require={
        'tests': [
            'pytest',
            'pytest-timeout',
            'pytest-asyncio'
        ]
    }
)
