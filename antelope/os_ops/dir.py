import os

class Directory():
    def ClearMakeDirectory(self, path:str):
        """不管目录存在与否，都重新创建目录。存在时清空目录内容"""
        if os.path.exists(path):
            os.system('rm -rf ' + path)
        os.makedirs(path, exist_ok= True)

    def MakeDirectory(self, path:str):
        """如果目录不存在，则创建"""
        if not os.path.exists(path):
            os.makedirs(path, exist_ok= True)

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