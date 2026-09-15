# Antelope

![](images/logo.png)



小巧敏捷的编译链接工具。专注于编译各类 c/c++ 项目，以生成静态库、共享库、可执行程序。


```bash
python3 antelope_install.py
```



切换到生成目录，如 `./test/`

```bash
# 初始化 antel.json
antel init
```



填写 antel.json 各项内容。其中各项含义如下表所示

| 参数名              | 含义                                                         |
| ------------------- | ------------------------------------------------------------ |
| projectName         | 项目名，任意字符，如 helloworld                              |
| source              | 参与项目编译的所有c/c++文件及头文件相对编译位置的路径，如 ["helloworld.c"] |
| include_directories | 项目需引入的编译路径                                         |
| target_type         | 生成的目标类型，可为 static，shared，exe。不区分大小写。     |
| compiler            | 所用编译器类型，可为 gcc，g++，gpp。不区分大小写。           |
| compile_args        | 传递给编译器的编译参数                                       |
| link_args           | 传递给连接器的链接参数                                       |
| analyze_files       | 要自动分析的 c/c++ 源文件                                    |



填写完毕后，执行命令

```bash
# 开始构建项目
antel rebuild
```



antel 可接受的参数如下表所示

| 参数名  | 含义                                           |
| ------- | ---------------------------------------------- |
| init    | 初始化 antel.json                              |
| build   | 构建项目差异部分                               |
| rebuild | 重新构建项目。不管项目有否被构建过，都重新构建 |
| clear   | 清理构建结果与所有中间文件                     |
| link    | 只链接而不编译                                 |
| analyze | 自动分析指定的 c/c++ 源文件                    |

