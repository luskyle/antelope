import json
import os
from prompt_toolkit.shortcuts import yes_no_dialog

class AntelJsonCpp():
    def __init__(self, projectName:str, target_type, compiler, fileName:str='antel.json'):
        self.projectName = projectName.strip().replace(' ', '_')
        self.targetType = target_type
        self.compiler = compiler
        self.fileName = fileName.strip().replace(' ', '_')

    def serialize(self):
        json_dict = dict()
        json_dict.update({"projectName":self.projectName})
        json_dict.update({"target_type":self.targetType})
        json_dict.update({"compiler":self.compiler})
        json_dict.update({"source":[]})
        json_dict.update({"exclude_source":[]})
        json_dict.update({"include_directories":[]})
        json_dict.update({"compile_args":[
            "-std=c++17",
            "-w",
            "-Os",
            # "-enable-inlining", 
            "-fno-rtti",
            "-fsized-deallocation",
            "-fno-weak",
            "-fPIC"
        ]})
        json_dict.update({"link_args":[
            # "-licuuc",
            # "-licui18n",
            # "-ldl"
        ]})
        json_dict.update({"compile_commands":True})
        json_dict.update({"report":False})

        if os.path.exists(f'./{self.fileName}'):
            result = yes_no_dialog(
                title='File Exist',
                text=f'Do you want to cover the {self.fileName} which exist already?'
            ).run()

            if result == True:
                with open(f'./{self.fileName}', 'w') as f:
                    json.dump(json_dict, f, indent=4)
        else:
                with open(f'./{self.fileName}', 'w') as f:
                    json.dump(json_dict, f, indent=4)