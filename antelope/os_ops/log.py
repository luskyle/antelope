import shutil

class Log():
    def __init__(self, output_dir:str):
        self.output_dir = output_dir

    def clearLog(self):
        """清除输出目录，包括生成目标与所有中间文件"""
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def writeLogfile(self, result, fileName):
        with open(f"{self.output_dir}/log/{fileName}", 'w') as f:
            f.writelines(result)