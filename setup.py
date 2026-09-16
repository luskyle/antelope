from setuptools import setup, find_packages

with open('README.md', encoding='utf-8') as readme:
    long_description = readme.read()

setup(name='antelope',
      version='1.0',
      author='zhanhui.lu',
      author_email='luzhanhui@boe.com.cn',
      description='小巧敏捷的编译链接工具。专注于编译各类 c/c++ 项目，以生成静态库、共享库、可执行程序。',
      long_description=long_description,
      long_description_content_type='text/markdown',
      license='Apache-2.0',
      classifiers=[
          'Programming Language :: Python :: 3',
          'Operating System :: POSIX :: Linux',
          'Topic :: Software Development :: Build Tools',
      ],
      python_requires='>=3.8',
      packages=find_packages(exclude=['tests']),
      install_requires=['hash_calc>=1.1.0',
                        'alive_progress>=3.1.1',
                        'prompt_toolkit>=3.0.38',
                        'click>=8.1.3'
                        ],
      extras_require={
          'test': ['pytest>=7.0']
      },
      entry_points={
      'console_scripts': [
            'antel = antelope.antelope:main'
        ]
      }
)