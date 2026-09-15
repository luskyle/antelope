import os

os.system('sudo pip uninstall antelope -y')
os.system('python3 setup.py bdist_wheel')
os.system('sudo pip install dist/antelope-1.0-py3-none-any.whl')
os.system('rm -rf ./build ./antelope.egg-info ./antelope/antelope.egg-info ./dist')