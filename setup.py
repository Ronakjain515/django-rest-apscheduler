from distutils.core import setup
setup(
  name = 'rest_apscheduler',
  packages = ['rest_apscheduler', 'rest_apscheduler/migrations'],
  version = '0.1.6',
  license='MIT',
  description = 'You can use this package only for django and can schedule jobs using any database and maintain record.',
  author = 'Ronak Jain',
  author_email = 'jronak515@gmail.com',
  url = 'https://github.com/Ronakjain515/django-rest-apscheduler.git',
  download_url = 'https://github.com/Ronakjain515/django-rest-apscheduler/archive/refs/tags/0.1.5.tar.gz',
  keywords = ['django', 'rest', 'restframework', 'apscheduler', 'scheduler'],
  install_requires=[
          'apscheduler'
      ],
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'Topic :: Software Development :: Build Tools',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
  ],
)
