#!/usr/bin/env python3
"""Probe the host C toolchain and generate json-c configuration headers."""

from __future__ import annotations

import ctypes
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(".")
SOURCE = ROOT / ".antel" / "refs" / "json-c"
OUTPUT = ROOT / ".antel" / "build" / "json-c-config"


def compiler_command() -> list[str]:
    return shlex.split(os.environ.get("CC", "cc"))


def can_compile(source: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="json-c-probe-") as directory:
        source_path = Path(directory) / "probe.c"
        output_path = Path(directory) / "probe"
        source_path.write_text(source, encoding="utf-8")
        result = subprocess.run(
            compiler_command()
            + [
                "-D_GNU_SOURCE",
                "-Werror=implicit-function-declaration",
                str(source_path),
                "-o",
                str(output_path),
                "-lm",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0


def header_available(header: str) -> bool:
    return can_compile(f"#include <{header}>\nint main(void) {{ return 0; }}\n")


def feature_macros() -> dict[str, int]:
    headers = [
        "dlfcn.h",
        "endian.h",
        "fcntl.h",
        "inttypes.h",
        "limits.h",
        "locale.h",
        "memory.h",
        "stdarg.h",
        "stdint.h",
        "stdlib.h",
        "strings.h",
        "string.h",
        "sys/cdefs.h",
        "sys/param.h",
        "sys/random.h",
        "sys/resource.h",
        "sys/stat.h",
        "sys/types.h",
        "syslog.h",
        "unistd.h",
        "getopt.h",
    ]
    macros = {
        "HAVE_" + re.sub(r"[^A-Za-z0-9]", "_", header).upper(): int(header_available(header))
        for header in headers
    }
    macros["JSON_C_HAVE_INTTYPES_H"] = macros["HAVE_INTTYPES_H"]
    macros["JSON_C_HAVE_STDINT_H"] = macros["HAVE_STDINT_H"]

    checks = {
        "HAVE_ARC4RANDOM": ("stdlib.h", "return (int)arc4random();"),
        "HAVE_OPEN": ("fcntl.h", "return open(\"/dev/null\", 0);"),
        "HAVE_REALLOC": ("stdlib.h", "void *p = realloc(0, 1); free(p); return 0;"),
        "HAVE_SETLOCALE": ("locale.h", "return setlocale(LC_ALL, \"C\") == 0;"),
        "HAVE_SNPRINTF": ("stdio.h", "char b[2]; return snprintf(b, sizeof(b), \"%s\", \"\") < 0;"),
        "HAVE_STRCASECMP": ("strings.h", "return strcasecmp(\"a\", \"A\");"),
        "HAVE_STRDUP": ("string.h", "char *p = strdup(\"x\"); free(p); return 0;"),
        "HAVE_STRERROR": ("string.h", "return strerror(0) == 0;"),
        "HAVE_STRNCASECMP": ("strings.h", "return strncasecmp(\"a\", \"A\", 1);"),
        "HAVE_USELOCALE": ("locale.h", "return uselocale((locale_t)0) == (locale_t)0;"),
        "HAVE_DUPLOCALE": ("locale.h", "locale_t l = duplocale((locale_t)0); return l == (locale_t)0;"),
        "HAVE_VASPRINTF": (
            "stdio.h",
            "int check(const char *f, ...) { va_list ap; char *p = 0; "
            "va_start(ap, f); int n = vasprintf(&p, f, ap); va_end(ap); "
            "free(p); return n < 0; }",
        ),
        "HAVE_VPRINTF": (
            "stdio.h",
            "int check(const char *f, ...) { va_list ap; va_start(ap, f); "
            "int r = vprintf(f, ap); va_end(ap); return r; }",
        ),
        "HAVE_VSNPRINTF": (
            "stdio.h",
            "int check(char *b, size_t n, const char *f, ...) { va_list ap; "
            "va_start(ap, f); int r = vsnprintf(b, n, f, ap); va_end(ap); return r; }",
        ),
        "HAVE_VSYSLOG": (
            "syslog.h",
            "void check(int p, const char *f, ...) { va_list ap; "
            "va_start(ap, f); vsyslog(p, f, ap); va_end(ap); }",
        ),
        "HAVE_GETRANDOM": ("sys/random.h", "char b; return (int)getrandom(&b, 1, 0);"),
        "HAVE_GETRUSAGE": ("sys/resource.h", "struct rusage r; return getrusage(RUSAGE_SELF, &r);"),
        "HAVE_STRTOLL": ("stdlib.h", "return strtoll(\"0\", 0, 10) != 0;"),
        "HAVE_STRTOULL": ("stdlib.h", "return strtoull(\"0\", 0, 10) != 0;"),
        "HAVE_DECL_INFINITY": ("math.h", "double d = INFINITY; return d == 0;"),
        "HAVE_DECL_ISINF": ("math.h", "return isinf(0.0);"),
        "HAVE_DECL_ISNAN": ("math.h", "return isnan(0.0);"),
        "HAVE_DECL_NAN": ("math.h", "double d = nan(\"\"); return d == 0;"),
        "HAVE_ATOMIC_BUILTINS": (
            "stddef.h",
            "int v = 0; return __sync_fetch_and_add(&v, 1);",
        ),
        "HAVE___THREAD": ("stddef.h", "__thread int value; int main(void) { return value; }"),
    }
    for name, (header, body) in checks.items():
        if name == "HAVE___THREAD":
            source = f"#include <{header}>\n{body}\n"
        elif name in {"HAVE_VASPRINTF", "HAVE_VPRINTF", "HAVE_VSNPRINTF", "HAVE_VSYSLOG"}:
            source = (
                f"#include <{header}>\n#include <stdarg.h>\n"
                "#include <stdlib.h>\n"
                f"int main(void) {{ return 0; }}\n{body}\n"
            )
        else:
            source = (
                f"#include <{header}>\n#include <stdlib.h>\n"
                f"int main(void) {{ {body} }}\n"
            )
        macros[name] = int(can_compile(source))
    return macros


def define(name: str, value: object = 1) -> str:
    return f"#define {name} {value}" if value is not None else f"#define {name}"


def render_config(macros: dict[str, int], version: str) -> str:
    lines = [
        "/* Generated by prepare_json_c.py. */",
        "#ifndef JSON_C_CONFIG_H",
        "#define JSON_C_CONFIG_H",
    ]
    for name, enabled in sorted(macros.items()):
        if enabled:
            numeric = name in {
                "HAVE_SYSLOG_H",
                "HAVE_SYS_PARAM_H",
                "HAVE_SYS_TYPES_H",
                "HAVE_UNISTD_H",
                "HAVE_VSYSLOG",
                "HAVE_STRCASECMP",
                "HAVE_STRNCASECMP",
                "JSON_C_HAVE_INTTYPES_H",
                "JSON_C_HAVE_STDINT_H",
            } or name.startswith("HAVE_DECL_")
            lines.append(define(name, 1 if numeric else None))

    lines.extend(
        [
            define("PACKAGE", '"json-c"'),
            define("PACKAGE_BUGREPORT", '"json-c@googlegroups.com"'),
            define("PACKAGE_NAME", '"json-c"'),
            define("PACKAGE_STRING", f'"json-c {version}"'),
            define("PACKAGE_TARNAME", '"json-c"'),
            define("PACKAGE_URL", '"https://github.com/json-c/json-c"'),
            define("PACKAGE_VERSION", f'"{version}"'),
            define("VERSION", f'"{version}"'),
            define("STDC_HEADERS"),
            define("SIZEOF_INT", ctypes.sizeof(ctypes.c_int)),
            define("SIZEOF_INT64_T", ctypes.sizeof(ctypes.c_int64)),
            define("SIZEOF_LONG", ctypes.sizeof(ctypes.c_long)),
            define("SIZEOF_LONG_LONG", ctypes.sizeof(ctypes.c_longlong)),
            define("SIZEOF_SIZE_T", ctypes.sizeof(ctypes.c_size_t)),
            define("SIZEOF_SSIZE_T", ctypes.sizeof(ctypes.c_ssize_t)),
        ]
    )
    if macros["HAVE___THREAD"]:
        lines.append(define("SPEC___THREAD", "__thread"))
    lines.append("#endif")
    return "\n".join(lines) + "\n"


def source_version() -> str:
    header = (SOURCE / "json_c_version.h").read_text(encoding="utf-8")
    match = re.search(r'#define JSON_C_VERSION "([0-9]+(?:\.[0-9]+){2})"', header)
    if match is None:
        raise RuntimeError("Could not read JSON_C_VERSION from upstream json_c_version.h")
    return match.group(1)


def write_headers() -> None:
    if not SOURCE.is_dir():
        raise FileNotFoundError(f"json-c source reference is missing: {SOURCE}")
    version = source_version()
    macros = feature_macros()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    (OUTPUT / "config.h").write_text(render_config(macros, version), encoding="utf-8")
    (OUTPUT / "json_config.h").write_text(
        "/* Generated by prepare_json_c.py. */\n"
        f"#define JSON_C_HAVE_INTTYPES_H {macros['JSON_C_HAVE_INTTYPES_H']}\n"
        f"#define JSON_C_HAVE_STDINT_H {macros['JSON_C_HAVE_STDINT_H']}\n",
        encoding="utf-8",
    )
    (OUTPUT / "json.h").write_text(
        """/* Generated by prepare_json_c.py. */
#ifndef _json_h_
#define _json_h_
#ifdef __cplusplus
extern "C" {
#endif
#include "arraylist.h"
#include "debug.h"
#include "json_c_version.h"
#include "json_object.h"
#include "json_object_iterator.h"
#include "json_patch.h"
#include "json_pointer.h"
#include "json_tokener.h"
#include "json_util.h"
#include "linkhash.h"
#ifdef __cplusplus
}
#endif
#endif
""",
        encoding="utf-8",
    )
    (OUTPUT / "apps_config.h").write_text(
        "/* Generated by prepare_json_c.py. */\n"
        + (define("HAVE_SYS_RESOURCE_H") + "\n" if macros["HAVE_SYS_RESOURCE_H"] else "")
        + (define("HAVE_GETRUSAGE") + "\n" if macros["HAVE_GETRUSAGE"] else "")
        + (define("HAVE_GETOPT_H") + "\n" if macros["HAVE_GETOPT_H"] else ""),
        encoding="utf-8",
    )


def main() -> None:
    write_headers()
    print(f"Generated json-c platform headers in {OUTPUT}")


if __name__ == "__main__":
    main()
