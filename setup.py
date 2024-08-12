from setuptools import setup, find_packages
import kaniko_deploy

def parse_requirements(filename):
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line and not line.startswith("#")]

with open('README.md', 'r',encoding='utf-8') as f:
    long_description=f.read()

setup(
    name=kaniko_deploy.__title__,
    version='1.2',
    author_email='nurdslab99@gmail.com',
    packages=find_packages(),
    install_requires=parse_requirements('requirements.txt'),
    python_requires='>=3.12',
    entry_points={
        'console_scripts': [
            'kaniko_deploy=kaniko_deploy.main:main',
        ],
    },
    license='MIT',
    long_description=long_description,
    long_description_content_type='text/markdown'
)