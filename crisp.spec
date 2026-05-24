# PyInstaller spec for a single-file Crisp build.
#
#   pip install -r requirements.txt
#   pyinstaller crisp.spec
#
# Produces dist/Crisp.exe (Windows). The bundled ffmpeg binary from
# imageio-ffmpeg is collected automatically via collect_dynamic_libs/data.

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# Bundle the ffmpeg binary that imageio-ffmpeg ships.
datas += collect_data_files("imageio_ffmpeg")
binaries += collect_dynamic_libs("imageio_ffmpeg")

# soundfile ships libsndfile as data; make sure it comes along.
datas += collect_data_files("soundfile")

# noisereduce/pyloudnorm sometimes need their submodules pinned.
hiddenimports += ["noisereduce", "pyloudnorm", "scipy.signal"]

a = Analysis(
    ["src/crisp/__main__.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "tkinter", "PyQt5", "PyQt6"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Crisp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no terminal window; it's a GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
