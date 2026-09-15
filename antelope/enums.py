from enum import Enum

class CompilerType(Enum):
    msvc = 0
    gxx = 1
    llvm = 2

class TargetType(Enum):
    Static = 0
    Shared = 1
    Executable = 2

class BuildType(Enum):
    Build = 0
    Rebuild = 1
    Unknown = 2