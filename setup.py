import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='aiflow',
    version='0.0.8',
    author='NuxTrade',
    description='Create composable AI agents',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
    py_modules=['flo'],
    package_dir={'': 'flo'},
    install_requires=[],
)
