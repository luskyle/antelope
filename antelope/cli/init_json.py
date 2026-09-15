from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import input_dialog
from prompt_toolkit.shortcuts import radiolist_dialog
from antelope.json_ops.antel_json_cpp import *

class InitJson():
    def createFromTemplate(self):
        fileName = input_dialog(
            title='file name',
            text='configuration file name:',
            default='antel.json'
        ).run()
        
        projectName = input_dialog(
            title='project name',
            text='input your project name:'
        ).run()

        targetType = radiolist_dialog(
            title="target type",
            text="select your build target:",
            values=[
                ("static", "make a static library"),
                ("shared", "make a shared library"),
                ("exe", "make a executable program")
            ]
        ).run()

        compilerType = radiolist_dialog(
            title="compiler type",
            text="select your compiler:",
            values=[
                ("gxx", "use gcc/g++ for building"),
                ("msvc", "use Microsoft compiler for building"),
                ("llvm", "use llvm compile collection for building")
            ]
        ).run()

        json = AntelJsonCpp(projectName, targetType, compilerType, fileName)
        json.serialize()
        print('初始化完成！')
