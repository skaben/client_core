from setuptools import setup, find_packages

with open("README.md", 'r') as f:
    long_description = f.read()


setup(
    name='skabenclient',
    version='0.4.2',
    description='SKABEN client ',
    license="MIT",
    long_description=long_description,
    author='Zerthmonk',
    author_email='me@tangled.link',
    url="dungeon.tangled.link",
    packages=['skabenclient'], 
    install_requires=[
        'pygame>=1.9.4',
        'paho-mqtt>=1.4.0',
        'pyaml>=19.0.0',
        'netifaces>=0.10.9',
        'skabenproto>=1.10'
    ],
    dependency_links=[
        'https://pypi.fury.io/zerthmonk/'
    ]
)

