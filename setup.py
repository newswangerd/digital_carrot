from setuptools import setup, find_packages

with open('README.md', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='digital_carrot',
    version='1.0.0',
    entry_points={
        'console_scripts': ['digital-carrot=digital_carrot.client:main'],
    },
    install_requires=["pydantic",],
    packages=find_packages(exclude=["tests", "tests.*"]),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/newswangerd/digital_carrot',
    description='Keep yourself accountable.'
)
