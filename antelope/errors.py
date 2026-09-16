class BuildError(Exception):
    """构建过程中可以预期的错误，出现时以非 0 退出码结束"""


class CommandError(BuildError):
    """外部命令以非 0 退出码结束时抛出"""

    def __init__(self, command:str, return_code:int, output:str='', reason:str=''):
        self.command = command
        self.return_code = return_code
        self.output = output

        message = f'命令执行失败(退出码 {return_code}): {command}'
        if reason != '':
            message += f' ({reason})'
        super().__init__(message)


class ConfigError(BuildError):
    """antel.json 内容不合法，或当前配置尚不支持时抛出"""