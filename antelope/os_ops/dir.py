import glob
import os
import shutil

class Directory():
    def ClearMakeDirectory(self, path:str):
        """不管目录存在与否，都重新创建目录。存在时清空目录内容"""
        shutil.rmtree(path, ignore_errors=True)
        os.makedirs(path, exist_ok= True)

    def MakeDirectory(self, path:str):
        """如果目录不存在，则创建"""
        if not os.path.exists(path):
            os.makedirs(path, exist_ok= True)

    def RemoveFiles(self, path:str, patterns:list):
        """删除目录下匹配给定通配模式的文件，用于清理上一轮的生成目标"""
        for pattern in patterns:
            for file in glob.glob(f'{path}/{pattern}'):
                try:
                    os.remove(file)
                except OSError as error:
                    print(f'清理 {file} 失败：{error}')

    def walkDir(self, path:str):
        result = []

        for root, dirs, files in os.walk(path):
            for file in files:
                result.append(file)
                # print(item)
        # self.writeLogfile(result, fileName)
        return result

    def walkDirFullPath(self, path:str):
        result = []

        for root, dirs, files in os.walk(path):
            for file in files:
                if root.endswith('/'):
                    result.append(root + file)
                else:
                    result.append(f'{root}/{file}')
                # print(item)
        # self.writeLogfile(result, fileName)
        return result