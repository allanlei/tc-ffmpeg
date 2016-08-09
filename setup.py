# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


setup(
    name='tc_ffmpeg',
    version='0.1.0',
    url='https://github.com/allanlei/tc_ffmpeg',
    license='MIT',
    author='Allan Lei',
    description='FFmpeg loader for Thumbor',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'thumbor>=5.0.6',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
