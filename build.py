"""One-command build.   Windows: py build.py     macOS: python3 build.py

Windows:
  dist\\Sahm\\Sahm.exe       the app, with yt-dlp / FFmpeg / Deno in dist\\Sahm\\tools
  dist\\Sahm-Portable.zip    no-install version
  dist\\Sahm-Setup.exe       installer (needs Inno Setup 6)
macOS (build on the kind of Mac you target - Apple Silicon or Intel):
  dist/Sahm.app             the app, video tools inside Sahm.app/Contents/MacOS/tools
  dist/Sahm-macOS-AppleSilicon.dmg  or  dist/Sahm-macOS-Intel.dmg
"""
import os
import sys
import shutil
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "app"))
import tools  # noqa: E402  (shared list of tool downloads for each platform)

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
PLATFORM = tools.platform_key()
VENDOR = os.path.join(ROOT, "vendor_tools", PLATFORM)

NOTICE = """These programs are included unmodified to provide video downloads:

yt-dlp  - Unlicense (public domain)   https://github.com/yt-dlp/yt-dlp
FFmpeg  - GPL v3, source code at      https://ffmpeg.org/download.html
          Windows builds:             https://github.com/yt-dlp/FFmpeg-Builds
          macOS builds:               https://ffmpeg.martin-riedl.de
Deno    - MIT license                 https://github.com/denoland/deno
"""


def step(msg):
    print("\n=== " + msg, flush=True)


def run(args):
    subprocess.check_call(args, cwd=ROOT)


def download(url, dest):
    def hook(blocks, bs, total):
        if total > 0:
            pct = min(100, blocks * bs * 100 // total)
            print(f"\r    {os.path.basename(dest)}: {pct}%  of {total / 1e6:.0f} MB", end="", flush=True)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "Sahm-build"})
    with urllib.request.urlopen(req) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        n = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            n += 1
            hook(n, 1 << 20, total)
    os.replace(tmp, dest)
    print()


def fetch_tools():
    """Download yt-dlp, FFmpeg (+ffprobe) and Deno for this platform into vendor_tools/<platform>."""
    sources = tools.TOOL_SOURCES.get(PLATFORM)
    if not sources:
        sys.exit(f"Video tools are only packaged for Windows and macOS (this is '{PLATFORM}').")
    os.makedirs(VENDOR, exist_ok=True)
    for name, parts in sources.items():
        if os.path.exists(os.path.join(VENDOR, name + tools.EXE)):
            print(f"    {name}: already downloaded")
            continue
        for i, (url, members) in enumerate(parts):
            tmp = os.path.join(VENDOR, f"{name}-{i}.download")
            try:
                download(url, tmp)
                got = tools.install_file(tmp, members, VENDOR, name + tools.EXE)
                if not got:
                    raise IOError(f"{members} not found inside the download")
            except Exception as e:  # noqa
                print(f"\n    WARNING: could not add {name} ({e}). The build continues; Sahm will download"
                      f" {name} by itself the first time a video is downloaded.")
                break
    with open(os.path.join(VENDOR, "THIRD-PARTY-NOTICES.txt"), "w") as f:
        f.write(NOTICE)


def copy_tools(dest, notices_dest=None):
    """Programs go to dest; the text notice goes to notices_dest (macOS: code and text must be apart)."""
    os.makedirs(dest, exist_ok=True)
    for f in os.listdir(VENDOR):
        if f.endswith(".txt") and notices_dest:
            os.makedirs(notices_dest, exist_ok=True)
            shutil.copy2(os.path.join(VENDOR, f), os.path.join(notices_dest, f))
            continue
        shutil.copy2(os.path.join(VENDOR, f), os.path.join(dest, f))
        tools.make_executable(os.path.join(dest, f)) if not f.endswith(".txt") else None


def pyinstaller(icon, extra=()):
    py = sys.executable
    run([py, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "Sahm",
         "--icon", os.path.join("app", "assets", icon),
         "--add-data", os.path.join("app", "assets") + os.pathsep + "assets",
         "--paths", "app", *extra, os.path.join("app", "main.py")])


# ------------------------------------------------------------------ Windows
def find_iscc():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        if base:
            p = os.path.join(base, "Inno Setup 6", "ISCC.exe")
            if os.path.exists(p):
                return p
    return shutil.which("ISCC")


def build_windows():
    step("Building Sahm.exe")
    pyinstaller("icon.ico")
    step("Adding video tools (downloaded on the first build only)")
    fetch_tools()
    copy_tools(os.path.join(ROOT, "dist", "Sahm", "tools"))
    step("Making the portable zip")
    shutil.make_archive(os.path.join(ROOT, "dist", "Sahm-Portable"), "zip",
                        root_dir=os.path.join(ROOT, "dist"), base_dir="Sahm")
    print("    dist\\Sahm-Portable.zip")
    iscc = find_iscc()
    if iscc:
        step("Building the installer")
        import browsers
        ids = []
        if "Edge" in browsers.configured():
            ids.append(f"/DEdgeId={browsers.EDGE_EXTENSION_ID}")
        if "Chrome" in browsers.configured():
            ids.append(f"/DChromeId={browsers.CHROME_EXTENSION_ID}")
        if not browsers.configured():
            print("    (extension store IDs not set in app/browsers.py - browsers won't offer it automatically)")
        run([iscc, *ids, "installer.iss"])
        print("\nDONE!  Installer: dist\\Sahm-Setup.exe")
    else:
        print("\nDONE!  App: dist\\Sahm\\Sahm.exe")
        print("Install Inno Setup 6 (https://jrsoftware.org/isdl.php) and run again to get Sahm-Setup.exe")


# ------------------------------------------------------------------ macOS
def build_mac():
    from settings import APP_VERSION
    step("Building Sahm.app")
    pyinstaller("icon.icns", ["--osx-bundle-identifier", "com.sahm.downloadmanager"])
    app = os.path.join(ROOT, "dist", "Sahm.app")
    plist = os.path.join(app, "Contents", "Info.plist")
    import plistlib
    with open(plist, "rb") as f:
        info = plistlib.load(f)
    info.update({"CFBundleDisplayName": "Sahm", "CFBundleShortVersionString": APP_VERSION,
                 "CFBundleVersion": APP_VERSION, "NSHighResolutionCapable": True,
                 "LSMinimumSystemVersion": "11.0", "NSHumanReadableCopyright": "Sahm Download Manager"})
    with open(plist, "wb") as f:
        plistlib.dump(info, f)

    step("Adding video tools (downloaded on the first build only)")
    fetch_tools()
    helpers = os.path.join(app, "Contents", "Helpers")
    copy_tools(helpers, notices_dest=os.path.join(app, "Contents", "Resources"))

    step("Signing (ad-hoc unless MAC_SIGN_IDENTITY is set to a Developer ID)")
    identity = os.environ.get("MAC_SIGN_IDENTITY", "-")
    hardened = [] if identity == "-" else ["--options", "runtime", "--timestamp"]
    for f in sorted(os.listdir(helpers)):                         # sign the helper programs first, then the app
        run(["codesign", "--force", "--sign", identity, *hardened, os.path.join(helpers, f)])
    run(["codesign", "--force", "--sign", identity, *hardened, app])
    if subprocess.call(["codesign", "--verify", "--deep", "--strict", "--verbose=2", app], cwd=ROOT) != 0:
        print("    WARNING: signature check reported a problem (the app still works; see the lines above)")

    step("Making the .dmg")
    label = "AppleSilicon" if PLATFORM == "mac-arm64" else "Intel"
    stage = os.path.join(ROOT, "dist", "dmg")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    run(["ditto", app, os.path.join(stage, "Sahm.app")])
    os.symlink("/Applications", os.path.join(stage, "Applications"))     # drag-to-install shortcut
    shutil.copytree(os.path.join(ROOT, "extension"), os.path.join(stage, "Browser extension"))
    dmg = os.path.join(ROOT, "dist", f"Sahm-macOS-{label}.dmg")
    if os.path.exists(dmg):
        os.remove(dmg)
    for attempt in range(1, 5):                                  # hdiutil is sometimes "Resource busy" on CI
        if subprocess.call(["hdiutil", "create", "-volname", "Sahm", "-srcfolder", stage,
                            "-ov", "-format", "UDZO", dmg], cwd=ROOT) == 0:
            break
        print(f"    hdiutil failed (attempt {attempt}), retrying in 10 s…")
        import time
        time.sleep(10)
    else:
        sys.exit("Could not create the .dmg")
    shutil.rmtree(stage, ignore_errors=True)
    print(f"\nDONE!  {os.path.relpath(dmg, ROOT)}")


def main():
    step("Installing Python packages")
    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    if IS_WIN:
        build_windows()
    elif IS_MAC:
        build_mac()
    else:
        sys.exit("Build on Windows or macOS (or let GitHub build both - see README).")


if __name__ == "__main__":
    main()
