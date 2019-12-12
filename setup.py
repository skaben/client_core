from setuptools import setup, find_packages

with open("README.md", 'r') as f:
    long_description = f.read()


setup(
    name='skabenclient',
    version='0.9.7',
    description='SKABEN client ',
    license="MIT",
    long_description=long_description,
    author='Zerthmonk',
    author_email='me@tangled.link',
    url="dungeon.tangled.link",
    packages=['skabenclient'], 
    install_requires=[
        'paho-mqtt==1.4.0',
        'pyaml==18.11.0',
        'netifaces==0.10.9',
        'skabenproto'  
    ],
    dependency_links=[
        'https://pypi.fury.io/zerthmonk/'
    ]
)

