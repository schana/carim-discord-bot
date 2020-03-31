from setuptools import setup, find_packages

setup(
    name='carim-discord-bot',
    version='1.0',
    packages=find_packages(),
    install_requires=['discord.py'],
    entry_points={'console_scripts': ['carim-bot=carim_discord_bot.main:main']},
    url='https://github.com/schana/carim-discord-bot',
    license='License :: OSI Approved :: Apache Software License',
    author='Nathaniel Schaaf',
    author_email='nathaniel.schaaf@gmail.com',
    description='Discord bot for Carim'
)
