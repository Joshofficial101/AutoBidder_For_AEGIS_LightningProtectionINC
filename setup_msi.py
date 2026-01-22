from cx_Freeze import setup, Executable
from packaging.version import Version
import cx_Freeze.hooks._pydantic_ as pydantic_hook

APP_NAME = "LightningBid"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "Lightning Protection Bidding System"
UPGRADE_CODE = "{8A6B8B9B-5A6B-4D0D-9B33-5B3A2E6C2E6E}"

build_exe_options = {
    "include_files": [
        ("assets", "assets"),
        ("data", "data"),
    ],
    "include_msvcr": True,
}

shortcut_table = [
    (
        "StartMenuShortcut",           # Shortcut
        "ProgramMenuFolder",           # Directory_
        APP_NAME,                      # Name
        "TARGETDIR",                   # Component_
        "[TARGETDIR]LightningBid.exe", # Target
        None,                          # Arguments
        APP_DESCRIPTION,               # Description
        None,                          # Hotkey
        "AppIcon",                     # Icon
        None,                          # IconIndex
        None,                          # ShowCmd
        "TARGETDIR",                   # WkDir
    ),
]

bdist_msi_options = {
    "upgrade_code": UPGRADE_CODE,
    "add_to_path": False,
    "all_users": False,
    "initial_target_dir": r"[LocalAppDataFolder]\LightningBid",
    "data": {
        "Shortcut": shortcut_table,
        "Icon": [("AppIcon", "assets/app_icon.ico")],
    },
}

executables = [
    Executable(
        "src/gui/run_gui.py",
        base="gui",
        target_name="LightningBid.exe",
        icon="assets/app_icon.ico",
    )
]

# Work around cx_Freeze pydantic hook version parsing (string vs tuple)
def _patched_pydantic(self, finder, module):
    module.global_names.update(
        [
            "BaseModel",
            "PydanticSchemaGenerationError",
            "PydanticUndefinedAnnotation",
            "PydanticUserError",
        ]
    )
    try:
        version = module.distribution.version
        if isinstance(version, str):
            if Version(version) < Version("2"):
                finder.include_module("colorsys")
                finder.include_module("datetime")
                finder.include_module("decimal")
                finder.include_module("functools")
                finder.include_module("ipaddress")
                finder.include_package("json")
                finder.include_module("pathlib")
                finder.include_module("uuid")
                with __import__("contextlib").suppress(ImportError):
                    finder.include_module("dataclasses")
                with __import__("contextlib").suppress(ImportError):
                    finder.include_module("typing_extensions")
        else:
            if version < (2,):
                finder.include_module("colorsys")
                finder.include_module("datetime")
                finder.include_module("decimal")
                finder.include_module("functools")
                finder.include_module("ipaddress")
                finder.include_package("json")
                finder.include_module("pathlib")
                finder.include_module("uuid")
                with __import__("contextlib").suppress(ImportError):
                    finder.include_module("dataclasses")
                with __import__("contextlib").suppress(ImportError):
                    finder.include_module("typing_extensions")
    except Exception:
        # If anything goes wrong, skip the version-specific additions.
        pass

pydantic_hook.Hook.pydantic = _patched_pydantic

setup(
    name=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    options={"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables=executables,
)

