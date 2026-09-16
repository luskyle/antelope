import glob
import os
import sys


def run(command:str):
    """执行安装步骤，失败即终止，避免留下半成品"""
    print(f'$ {command}')
    if os.system(command) != 0:
        print(f'安装失败：{command}')
        sys.exit(1)


# 未安装过时卸载命令会返回非 0，此处不视为失败
os.system('sudo pip uninstall antelope -y')

run(f'{sys.executable} -m pip wheel . --no-deps -w dist')

wheels = glob.glob('dist/antelope-*.whl')
if wheels.__len__() == 0:
    print('未生成 wheel 包，安装终止')
    sys.exit(1)

run(f'sudo pip install --force-reinstall {wheels[0]}')
run('rm -rf ./build ./antelope.egg-info ./antelope/antelope.egg-info ./dist')
print('安装完成：' + wheels[0])