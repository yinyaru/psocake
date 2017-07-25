#coding: utf8

"""
Setup script for psocake.
"""

from glob import glob
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(name='psocake',
      version='0.2.0',
      author="Chun Hong Yoon",
      author_email="yoon82@slac.stanford.edu",
      description='GUI for SFX/SPI',
      url='https://github.com/lcls-psana/psocake',
      packages=["psocake"],
      package_dir={"psocake": "psocake"},
      scripts=[s for s in glob('app/*') if not s.endswith('__.py')])