import json
import os

from hash_calc.HashCalc import HashCalc

class CalcHash:

    def __init__(self, files_global:list, output_dir:str='.'):
        self.files = list(files_global)
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

    def currentHashes(self):
        """当前存在的输入文件与其 md5。目录与已删除的文件不参与基线"""
        return {item: self.GetMd5(item) for item in self.files if os.path.isfile(item)}

    def hashLines(self, hashes:dict):
        return [json.dumps({item: hashes[item]}) + '\n' for item in hashes]

    def readBaseline(self):
        """
        读取上次构建的 hash 基线。
        旧版本基线为 python 字面量格式，读不出时按无基线处理，效果等同于全量重新构建
        """
        baseline = {}
        if not os.path.exists(self.hashFilePath):
            return baseline

        with open(self.hashFilePath) as file:
            for line in file.readlines():
                line = line.strip()
                if line == '':
                    continue
                try:
                    baseline.update(json.loads(line))
                except json.JSONDecodeError:
                    print('hash 基线格式无法识别，本次按全量构建处理...')
                    return {}
        return baseline

    def compute_new_Md5(self):
        """把当前输入文件的 hash 记为基线，作为下次构建的比较基准"""
        print('更新文件 hash 基线...')
        self.diff = {}
        self.writeLogfile(self.hashLines(self.currentHashes()), self.fileName)

    def GetChangedFiles(self):
        """返回相对基线发生变化的文件：新增、内容变化、基线中已消失的都会返回"""
        print('计算文件 hash...')
        current_hashes = self.currentHashes()
        baseline = self.readBaseline()

        changed = {}
        for item in set(current_hashes) | set(baseline):
            if current_hashes.get(item) != baseline.get(item):
                changed.update({item: {'baseline': baseline.get(item), 'current': current_hashes.get(item)}})

        self.diff = changed
        self.writeLogfile([json.dumps(self.diff, indent=4)], 'hashes_diff')
        print('发生变化的文件：' + str(self.diff.__len__()))
        return list(self.diff.keys())