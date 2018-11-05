"""
Arduino

Arduino Wiring-based Framework allows writing cross-platform software to
control devices attached to a wide range of Arduino boards to create all
kinds of creative coding, interactive objects, spaces or physical experiences.

https://github.com/arduino/ArduinoCore-mbed
"""

import os

from SCons.Script import DefaultEnvironment

env = DefaultEnvironment()
platform = env.PioPlatform()
board = env.BoardConfig()

FRAMEWORK_DIR = platform.get_package_dir("framework-arduino-mbed")
assert os.path.isdir(FRAMEWORK_DIR)


def load_flags(filename):
    if not filename:
        return []

    file_path = os.path.join(FRAMEWORK_DIR, "variants", board.get(
        "build.variant"), "%s.txt" % filename)
    if not os.path.isfile(file_path):
        print("Warning: Couldn't find file '%s'" % file_path)
        return []

    with open(file_path, "r") as fp:
        return [f.strip() for f in fp.readlines() if f.strip()]


def configure_flash_layout(board_config):
    # Currently only Portenta board needs this functionality
    board_id = env.subst("$BOARD")
    if not board_id.startswith("portenta_h7"):
        return

    flash_layout = board_config.get("build.arduino.flash_layout", "50_50")
    defines = []
    if flash_layout == "50_50":
        defines.append(("CM4_BINARY_START", "0x08100000"))
        if board_id == "portenta_h7_m4":
            defines.append(("CM4_BINARY_END", "0x08200000"))
    elif flash_layout == "75_25":
        defines.append(("CM4_BINARY_START", "0x08180000"))
        if board_id == "portenta_h7_m4":
            board_config.update("upload.offset_address", "0x08180000")
            defines.append(("CM4_BINARY_END", "0x08200000"))
    elif flash_layout == "100_0":
        defines.append(("CM4_BINARY_START", "0x60000000"))
        if board_id == "portenta_h7_m4":
            defines.extend(
                [("CM4_BINARY_END", "0x60040000"), ("CM4_RAM_END", "0x60080000")]
            )

    env.Append(
        LINKFLAGS=["-D%s=%s" % (name, value) for name, value in defines],
        CPPDEFINES=defines,
    )


cflags = set(load_flags("cflags"))
cxxflags = set(load_flags("cxxflags"))
ccflags = cflags.intersection(cxxflags)

env.Append(
    ASFLAGS=[f for f in ccflags if isinstance(f, str) and f.startswith("-m")],
    ASPPFLAGS=["-x", "assembler-with-cpp"],

    CFLAGS=sorted(list(cflags - ccflags)),

    CCFLAGS=sorted(list(ccflags)),

    CPPDEFINES=[d.replace("-D", "") for d in load_flags("defines")],

    CXXFLAGS=sorted(list(cxxflags - ccflags)),

    LIBPATH=[
        os.path.join(FRAMEWORK_DIR, "variants", board.get("build.variant")),
        os.path.join(FRAMEWORK_DIR, "variants", board.get("build.variant"), "libs")
    ],

    LINKFLAGS=load_flags("ldflags"),

    LIBSOURCE_DIRS=[os.path.join(FRAMEWORK_DIR, "libraries")],

    LIBS=["mbed"]
)

if board.get("build.mcu", "").startswith("nrf52840"):
    env.Append(LIBS=["cc_310_core", "cc_310_ext", "cc_310_trng"])

env.Append(
    # Due to long path names "-iprefix" hook is required to avoid toolchain crashes
    CCFLAGS=[
        "-iprefix" + os.path.join(FRAMEWORK_DIR, "cores", board.get("build.core")),
        "@%s" % os.path.join(FRAMEWORK_DIR, "variants", board.get(
            "build.variant"), "includes.txt"),
        "-nostdlib"
    ],

    CPPDEFINES=[
        ("ARDUINO", 10810),
        "ARDUINO_ARCH_MBED"
    ],

    CPPPATH=[
        os.path.join(FRAMEWORK_DIR, "cores", board.get("build.core")),
        os.path.join(FRAMEWORK_DIR, "cores", board.get(
            "build.core"), "api", "deprecated"),
        os.path.join(FRAMEWORK_DIR, "cores", board.get(
            "build.core"), "api", "deprecated-avr-comp")
    ],

    LINKFLAGS=[
        "--specs=nano.specs",
        "--specs=nosys.specs",
        "-Wl,--as-needed"
    ]
)

#
# Configure dynamic memory layout
#

configure_flash_layout(board)

#
# Linker requires preprocessing with specific defines
#

if not board.get("build.ldscript", ""):
    ldscript = os.path.join(
        FRAMEWORK_DIR, "variants", board.get("build.variant"), "linker_script.ld")
    if board.get("build.mbed.ldscript", ""):
        ldscript = env.subst(board.get("build.arduino.ldscript"))
    if os.path.isfile(ldscript):
        preprocessed_linker_script = env.Command(
            os.path.join(
                "$BUILD_DIR", "cpp.linker_script.ld"
            ),
            ldscript,
            env.VerboseAction(
                "$CXX -E -P -x c %s $SOURCE -o $TARGET"
                % " ".join(f for f in env["LINKFLAGS"] if f.startswith("-D")),
                "Generating LD script $TARGET",
            ),
        )

        env.Depends("$BUILD_DIR/$PROGNAME$PROGSUFFIX", preprocessed_linker_script)
        env.Replace(LDSCRIPT_PATH=preprocessed_linker_script)
    else:
        print("Warning! Couldn't find linker script file!")

# Framework requires all symbols from mbed libraries
env.Prepend(_LIBFLAGS="-Wl,--whole-archive ")
env.Append(_LIBFLAGS=" -Wl,--no-whole-archive -lstdc++ -lsupc++ -lm -lc -lgcc -lnosys")

libs = []

if "build.variant" in board:
    env.Append(CPPPATH=[
        os.path.join(FRAMEWORK_DIR, "variants", board.get("build.variant"))
    ])

    libs.append(
        env.BuildLibrary(
            os.path.join("$BUILD_DIR", "FrameworkArduinoVariant"),
            os.path.join(FRAMEWORK_DIR, "variants", board.get("build.variant"))))

libs.append(
    env.BuildLibrary(
        os.path.join("$BUILD_DIR", "FrameworkArduino"),
        os.path.join(FRAMEWORK_DIR, "cores", board.get("build.core"))))

env.Prepend(LIBS=libs)
