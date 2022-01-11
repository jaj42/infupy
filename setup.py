from setuptools import setup

setup(name         = 'infupy',
      version      = '2022.1.11',
      description  = 'Syringe pump infusion',
      url          = 'https://github.com/jaj42/infupy',
      author       = 'Jona Joachim',
      author_email = 'jona@joachim.cc',
      license      = 'ISC',
      packages     = ['infupy', 'infupy.backends', 'infupy.gui'],
      install_requires=[
          'pyserial',
          'crcmod',
          'qtpy'
      ],
      scripts = [
          'scripts/syre.pyw'
      ]
)
