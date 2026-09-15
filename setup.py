from setuptools import setup,find_packages

setup(name='antelope',
      version='1.0',
      author='zhanhui.lu',
      author_email='luzhanhui@boe.com.cn',
      description='小巧敏捷的编译链接工具。专注于编译各类 c/c++ 项目，以生成静态库、共享库、可执行程序。',
      py_modules=['antelope', 'md5', 'enums'],
      packages=['antelope', 'antelope.analyze', 'antelope.args_parser', 
                'antelope.cli', 'antelope.compiler', 'antelope.linker',
                'antelope.os_ops', 'antelope.json_ops', 'antelope/runner'
                ],
      install_requires=['hash_calc>=1.1.0',
                        'alive_progress>=3.1.1',
                        'prompt_toolkit>=3.0.38',
                        'click>=8.1.3'
                        ],
      entry_points={
      'console_scripts': [
            'antel = antelope.antelope:main'
        ]
      }
)
