import shlex
import shutil
import subprocess
import sys

from antelope.errors import *

class Command():
    """
    统一的外部命令执行入口。非 0 退出码一律抛 CommandError，避免失败被当成成功。

    内部一律以参数列表（argv）为单位，不再把命令拼成字符串再切分——这样含空格或引号的
    路径与参数不会被走样。字符串入口 run() 仅为兼容保留，内部实现同样转成 argv。

    redirect_to 为空且不要求 echo 时，输出直接透传到终端，便于实时看到编译诊断信息。
    """

    def run(self, command:str, redirect_to:str='', echo:bool=False):
        return self.run_argv(shlex.split(command), redirect_to, echo)

    def run_argv(self, argv:list, redirect_to:str='', echo:bool=False, capture:bool=False):
        if argv.__len__() == 0:
            raise CommandError('', 127, reason='空命令')

        if shutil.which(argv[0]) is None:
            raise CommandError(shlex.join(argv), 127, reason=f'命令不存在或不可执行：{argv[0]}')

        if redirect_to == '' and not echo and not capture:
            return self.runInheritOutput(argv)
        return self.runCaptureOutput(argv, redirect_to, echo)

    def runInheritOutput(self, argv:list):
        return_code = subprocess.call(argv)
        if return_code != 0:
            raise CommandError(shlex.join(argv), return_code)
        return ''

    def runCaptureOutput(self, argv:list, redirect_to:str, echo:bool):
        call = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, err = call.communicate()
        output = bytes.decode(out) if out else ''

        if redirect_to != '':
            with open(redirect_to, 'w') as f:
                f.write(output)

        if echo and output != '':
            sys.stdout.write(output)
            sys.stdout.flush()

        if call.returncode != 0:
            raise CommandError(shlex.join(argv), call.returncode, output)

        return output