from hash_calc.HashCalc import HashCalc
import os

files = []

class CalcHash:

    def __init__(self, files_global:list, output_dir:str='.'):
        global files
        files = files_global
        self.fileName = 'hashes'
        self.hashFilePath = f'{output_dir}/log/' + self.fileName
        self.diff = {}
        self.outputDir = output_dir

    def GetMd5(self, filePath:str):
        hash = HashCalc(filePath)
        return hash.md5
    
    def writeLogfile(self, result, fileName):
        with open(f"{self.outputDir}/log/" + fileName, 'w') as f:
            f.writelines(result)

    def compute_new_Md5(self):
        print('重新计算文件 hash...')
        new_hashes = [str({item:self.GetMd5(item)}) + '\n' for item in files]
        self.diff = {}
        self.writeLogfile(new_hashes, 'hashes')

    def GetMd5List(self):
        print('计算文件 hash...')

        if os.path.exists(self.hashFilePath):
            old_hashes = []
            with open(self.hashFilePath) as file:
                old_hashes = file.readlines()
            
            current_hashes = {item:self.GetMd5(item) for item in files}

            for old_hash in old_hashes:
                key = list(eval(old_hash).keys())[0]
                value = list(eval(old_hash).values())[0]
                if current_hashes.get(key) != value:
                    self.diff.update({key:value})

            self.writeLogfile(self.diff, 'hashes_diff')
        else:
            new_hashes = [str({item:self.GetMd5(item)}) + '\n' for item in files]
            self.diff = {}
            self.writeLogfile(new_hashes, self.fileName)