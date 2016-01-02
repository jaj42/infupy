from setuptools import setup

setup(name         = 'infupy',
      version      = '0.1',
      description  = 'Syringe pump infusion',
      url          = 'https://github.com/jaj42/infupy',
      author       = 'Jona Joachim',
      author_email = 'jona@joachim.cc',
      license      = 'ISC',
      packages     = ['infupy', 'infupy.backends'],
      install_requires=[
          'pyserial',
      ])
