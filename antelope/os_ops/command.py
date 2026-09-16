import shlex
import shutil
import subprocess
import sys

from antelope.errors import *

class Command():
    """
    统一的外部命令执行入口。非 0 退出码一律抛 CommandError，避免失败被当成成功。

    redirect_to 为空且不要求 echo 时，输出直接透传到终端，便于实时看到编译诊断信息。
    """

    def run(self, command:str, redirect_to:str='', echo:bool=False):
        args = shlex.split(command)
        if shutil.which(args[0]) is None:
            raise CommandError(command, 127, reason=f'命令不存在或不可执行：{args[0]}')

        if redirect_to == '' and not echo:
            return self.runInheritOutput(command, args)
        return self.runCaptureOutput(command, args, redirect_to, echo)

    def runInheritOutput(self, command:str, args:list):
        return_code = subprocess.call(args)
        if return_code != 0:
            raise CommandError(command, return_code)
        return ''

    def runCaptureOutput(self, command:str, args:list, redirect_to:str, echo:bool):
        call = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, err = call.communicate()
        output = bytes.decode(out) if out else ''

        if redirect_to != '':
            with open(redirect_to, 'w') as f:
                f.write(output)

        if echo and output != '':
            sys.stdout.write(output)
            sys.stdout.flush()

        if call.returncode != 0:
            raise CommandError(command, call.returncode, output)

        return output