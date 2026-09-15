import os

class Log():
    def __init__(self, output_dir:str='.'):
        self.output_dir = output_dir

    def clearLog(self):
        os.system(f'rm -rf {self.output_dir}')

    def writeLogfile(self, result, fileName):
        with open(f"{self.output_dir}/log/{fileName}", 'w') as f:
            f.writelines(result)