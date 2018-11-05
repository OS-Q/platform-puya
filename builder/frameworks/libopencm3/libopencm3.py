"""
libOpenCM3

The libOpenCM3 framework aims to create a free/libre/open-source
firmware library for various ARM Cortex-M0(+)/M3/M4 microcontrollers,
including ST STM32, Ti Tiva and Stellaris, NXP LPC 11xx, 13xx, 15xx,
17xx parts, Atmel SAM3, Energy Micro EFM32 and others.

http://www.libopencm3.org
"""

from __future__ import absolute_import

import re
from os import listdir, sep, walk
from os.path import isdir, isfile, join, normpath

from SCons.Script import DefaultEnvironment

from platformio.proc import exec_command

env = DefaultEnvironment()
board = env.BoardConfig()
MCU = board.get("build.mcu")

FRAMEWORK_DIR = env.PioPlatform().get_package_dir("framework-libopencm3")
assert isdir(FRAMEWORK_DIR)


def find_ldscript(src_dir):
    ldscript = None
    matches = []
    for item in sorted(listdir(src_dir)):
        _path = join(src_dir, item)
        if not isfile(_path) or not item.endswith(".ld"):
            continue
        matches.append(_path)

    if len(matches) == 1:
        ldscript = matches[0]
    elif isfile(join(src_dir, board.get("build.libopencm3.ldscript", ""))):
        ldscript = join(src_dir, board.get("build.libopencm3.ldscript"))

    return ldscript


def generate_nvic_files():
    for root, _, files in walk(join(FRAMEWORK_DIR, "include", "libopencm3")):
        if "irq.json" not in files or isfile(join(root, "nvic.h")):
            continue

        exec_command(
            [env.subst("$PYTHONEXE"), join("scripts", "irq2nvic_h"),
             join("." + root.replace(FRAMEWORK_DIR, ""),
                  "irq.json").replace("\\", "/")],
            cwd=FRAMEWORK_DIR
        )


def parse_makefile_data(makefile):
    data = {"includes": [], "objs": [], "vpath": ["./"]}

    with open(makefile) as f:
        content = f.read()

        # fetch "includes"
        re_include = re.compile(r"^include\s+([^\r\n]+)", re.M)
        for match in re_include.finditer(content):
            data["includes"].append(match.group(1))

        # fetch "vpath"s
        re_vpath = re.compile(r"^VPATH\s*\+?=\s*([^\r\n]+)", re.M)
        for match in re_vpath.finditer(content):
            data["vpath"] += match.group(1).split(":")

        # fetch obj files
        objs_match = re.search(
            r"^OBJS\s*\+?=\s*([^\.]+\.o\s*(?:\s+\\s+)?)+", content, re.M)
        assert objs_match
        data["objs"] = re.sub(
            r"(OBJS|[\+=\\\s]+)", "\n", objs_match.group(0)).split()
    return data


def get_source_files(src_dir):
    mkdata = parse_makefile_data(join(src_dir, "Makefile"))

    for include in mkdata["includes"]:
        _mkdata = parse_makefile_data(normpath(join(src_dir, include)))
        for key, value in _mkdata.items():
            for v in value:
                if v not in mkdata[key]:
                    mkdata[key].append(v)

    sources = []
    for obj_file in mkdata["objs"]:
        src_file = obj_file[:-1] + "c"
        for search_path in mkdata["vpath"]:
            src_path = normpath(join(src_dir, search_path, src_file))
            if isfile(src_path):
                sources.append(join("$BUILD_DIR", "FrameworkLibOpenCM3",
                                    src_path.replace(FRAMEWORK_DIR + sep, "")))
                break
    return sources


def generate_ldscript(variant):
    result = exec_command([
        env.subst("$PYTHONEXE"),
        join(FRAMEWORK_DIR, "scripts", "genlink.py"),
        join(FRAMEWORK_DIR, "ld", "devices.data"),
        variant, "DEFS"
    ])

    device_symbols = ""
    if result["returncode"] == 0:
        device_symbols = result["out"]
        assert all(f in device_symbols for f in ("_ROM_OFF", "_RAM_OFF"))
        # Fall back to values from board manifest if genlink failed
        if "-D_ROM=" not in device_symbols:
            device_symbols = device_symbols + " -D_ROM=%d" % board.get(
                "upload.maximum_size", 0)
        if "-D_RAM=" not in device_symbols:
            device_symbols = device_symbols + " -D_RAM=%d" % board.get(
                "upload.maximum_ram_size", 0)
    else:
        print("Warning! Couldn't generate linker script for %s" % variant)
        print(result["out"])
        print(result["err"])

    cmd = "$CC -P -E $SOURCE -o $TARGET " + device_symbols + " " + " ".join(
        [f for f in env["CCFLAGS"] if f.startswith("-m")])

    return env.Command(
        join("$BUILD_DIR", "generated.%s.ld" % variant),
        join(FRAMEWORK_DIR, "ld", "linker.ld.S"),
        env.VerboseAction(cmd, "Generating linker script $TARGET")
    )


def get_ld_device(platform):
    ld_device = MCU
    if platform == "ststm32":
        ld_device = ld_device[0:11]
    # Script cannot generate precise scripts for the following platforms.
    # Instead family and memory sizes from board manifest are used
    elif platform == "titiva":
        ld_device = "lm4f"

    return board.get("build.libopencm3.ld_device", ld_device)


#
# Processing ...
#


platform = env.subst("$PIOPLATFORM")
root_dir = join(FRAMEWORK_DIR, "lib")
variant = MCU
if platform == "titiva":
    env.Append(CPPDEFINES=["LM4F"])
    root_dir = join(root_dir, "lm4f")
elif platform == "ststm32":
    variant = MCU[0:7]
    root_dir = join(root_dir, "stm32", MCU[5:7])
    env.AppendUnique(CPPDEFINES=[variant.upper()])
elif platform == "nxplpc":
    variant = MCU[0:5] + "xx"
    root_dir = join(root_dir, variant)
    env.AppendUnique(CPPDEFINES=[variant.upper()])
elif platform == "siliconlabsefm32":
    root_dir = join(root_dir, "efm32", MCU[5:7])
    env.AppendUnique(CPPDEFINES=[MCU[0:7].upper()])

generate_nvic_files()

machine_flags = [
    "-mthumb",
    "-mcpu=%s" % board.get("build.cpu"),
]

env.Append(
    ASFLAGS=machine_flags,
    ASPPFLAGS=[
        "-x", "assembler-with-cpp",
    ],

    CFLAGS=[
        "-Wimplicit-function-declaration",
        "-Wmissing-prototypes",
        "-Wstrict-prototypes"
    ],

    CCFLAGS=machine_flags + [
        "-Os",  # optimize for size
        "-ffunction-sections",  # place each function in its own section
        "-fdata-sections",
        "-Wall",
        "-Wextra",
        "-Wredundant-decls",
        "-Wshadow",
        "-fno-common",
    ],

    CXXFLAGS=[
        "-fno-rtti",
        "-fno-exceptions"
    ],

    CPPDEFINES=[
        ("F_CPU", "$BOARD_F_CPU"),
        board.get("build.libopencm3.variant", "").upper()
    ],

    CPPPATH=[
        FRAMEWORK_DIR,
        join(FRAMEWORK_DIR, "include")
    ],

    LINKFLAGS=machine_flags + [
        "-Os",
        "-Wl,--gc-sections",
        "-nostartfiles",
        "--static",
        "--specs=nano.specs",
        "--specs=nosys.specs"
    ],

    LIBS=["c", "gcc", "m", "stdc++", "nosys"],

    LIBPATH=[
        join(FRAMEWORK_DIR, "lib")
    ]
)

if board.get("build.cpu", "") in ("cortex-m4", "cortex-m7"):
    fpv_version = "4-sp"
    if MCU.startswith("stm32h7"):
        fpv_version = "5"
    elif board.get("build.cpu", "") == "cortex-m7":
        fpv_version = "5-sp"

    env.Append(
        ASFLAGS=[
            "-mfloat-abi=hard",
            "-mfpu=fpv%s-d16" % fpv_version
        ],

        CCFLAGS=[
            "-mfloat-abi=hard",
            "-mfpu=fpv%s-d16" % fpv_version
        ],

        LINKFLAGS=[
            "-mfloat-abi=hard",
            "-mfpu=fpv%s-d16" % fpv_version
        ]
    )

if not board.get("build.ldscript", ""):
    ldscript = generate_ldscript(get_ld_device(platform))
    env.Depends("$BUILD_DIR/$PROGNAME$PROGSUFFIX", ldscript)
    env.Replace(LDSCRIPT_PATH=ldscript[0])

env.VariantDir(
    join("$BUILD_DIR", "FrameworkLibOpenCM3"),
    FRAMEWORK_DIR,
    duplicate=False
)

env.Append(
    LIBS=[
        env.Library(
            join("$BUILD_DIR", "FrameworkLibOpenCM3"),
            get_source_files(root_dir))
    ]
)
