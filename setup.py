from setuptools import setup, find_packages

with open("README.md", 'r') as f:
    long_description = f.read()

with open('requirements.txt', 'r') as f:
    requirements_list = f.readlines()


setup(
    name='skabenclient',
    version='1.17.2',
    description='SKABEN client ',
    license="MIT",
    long_description=long_description,
    author='Zerthmonk',
    author_email='zerthmonk@pm.me',
    url="dungeon.tangled.link",
    packages=['skabenclient'], 
    install_requires=requirements_list,
    dependency_links=[
        'https://pypi.fury.io/zerthmonk/'
    ]
)

