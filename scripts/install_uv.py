import os
import platform
import subprocess
import sys
import shutil
import ctypes


def get_install_dir() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".local", "bin")


def install_uv():
    system = platform.system().lower()
    install_dir = get_install_dir()

    # Pre-check: if uv is already installed (either on PATH or at expected location),
    # skip installation and just ensure PATH is configured.
    existing = detect_uv_binary(system, install_dir)
    if existing:
        print(f"uv already installed at: {existing}. Skipping installation.")
        ensure_on_path(system, os.path.dirname(existing) if os.path.isfile(existing) else existing)
        print("uv PATH setup verified")
        return

    # Create target dir only if we need to install
    os.makedirs(install_dir, exist_ok=True)

    env = os.environ.copy()
    # We'll manage PATH updates ourselves for consistency
    env["UV_NO_MODIFY_PATH"] = "1"

    if system == "windows":
        # Install uv to ~/.local/bin on Windows
        env["UV_INSTALL_DIR"] = install_dir
        cmd = [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "ByPass",
            "-Command",
            "irm https://astral.sh/uv/install.ps1 | iex",
        ]
    else:
        # Prefer unmanaged install so we control PATH updates
        env["UV_UNMANAGED_INSTALL"] = install_dir
        cmd = [
            "bash",
            "-c",
            "curl -LsSf https://astral.sh/uv/install.sh | sh",
        ]

    subprocess.run(cmd, check=True, env=env)
    print("uv installation script executed")

    # Verify where uv was installed
    uv_binary = os.path.join(install_dir, "uv.exe" if system == "windows" else "uv")
    if not os.path.exists(uv_binary):
        # Fallback: try to detect via current PATH
        found = shutil.which("uv")
        if found:
            install_dir_detected = os.path.dirname(found)
            print(f"Detected uv at {found}")
            ensure_on_path(system, install_dir_detected)
            return
        else:
            print(f"Warning: uv binary not found at expected location: {uv_binary}")
            # Still ensure expected install_dir is on PATH
            ensure_on_path(system, install_dir)
            return

    ensure_on_path(system, install_dir)
    print("uv installation and PATH setup complete")


def ensure_on_path(system: str, dir_path: str):
    dir_path = os.path.normpath(dir_path)
    # Update current process PATH for immediate availability in this session
    os.environ["PATH"] = dir_path + os.pathsep + os.environ.get("PATH", "")

    if system == "windows":
        add_to_path_windows(dir_path)
    else:
        add_to_path_posix(dir_path)


def add_to_path_windows(dir_path: str):
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE
        ) as key:
            try:
                current_value, value_type = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_value = os.environ.get("PATH", "")
                value_type = winreg.REG_EXPAND_SZ

            parts = [p.strip() for p in current_value.split(";") if p.strip()]
            if dir_path not in parts:
                sep = ";" if current_value and not current_value.endswith(";") else ""
                new_value = f"{current_value}{sep}{dir_path}"
                winreg.SetValueEx(key, "Path", 0, value_type, new_value)
                # Broadcast environment change to notify running shells
                try:
                    HWND_BROADCAST = 0xFFFF
                    WM_SETTINGCHANGE = 0x001A
                    SMTO_ABORTIFHUNG = 0x0002
                    res = ctypes.c_ulong()
                    ctypes.windll.user32.SendMessageTimeoutW(
                        HWND_BROADCAST,
                        WM_SETTINGCHANGE,
                        0,
                        ctypes.c_wchar_p("Environment"),
                        SMTO_ABORTIFHUNG,
                        5000,
                        ctypes.byref(res),
                    )
                except Exception as e:
                    print(f"Note: could not broadcast env change: {e}")
                print(f"Added '{dir_path}' to user PATH.")
            else:
                print(f"'{dir_path}' already present in user PATH.")
    except Exception as e:
        print(f"Failed to update PATH on Windows: {e}")


def add_to_path_posix(dir_path: str):
    home = os.path.expanduser("~")
    line = f'export PATH="{dir_path}:$PATH"'
    candidates = []

    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        candidates = [os.path.join(home, ".zshrc"), os.path.join(home, ".profile")]
    elif "bash" in shell:
        candidates = [os.path.join(home, ".bashrc"), os.path.join(home, ".profile")]
    else:
        candidates = [os.path.join(home, ".profile")]

    for rc in candidates:
        try:
            content = ""
            if os.path.exists(rc):
                with open(rc, "r", encoding="utf-8") as f:
                    content = f.read()
            if line not in content:
                with open(rc, "a", encoding="utf-8") as f:
                    f.write("\n# uv: ensure binary path on PATH\n")
                    f.write(line + "\n")
                print(f"Updated PATH in {rc}")
            else:
                print(f"PATH already configured in {rc}")
        except Exception as e:
            print(f"Failed to update {rc}: {e}")


def detect_uv_binary(system: str, install_dir: str) -> str | None:
    """Return full path to existing uv binary if present, else None.
    Checks current PATH first, then the expected install directory.
    """
    found = shutil.which("uv")
    if found:
        return found

    candidate = os.path.join(install_dir, "uv.exe" if system == "windows" else "uv")
    if os.path.exists(candidate):
        return candidate

    # If the folder exists and likely contains uv-managed files, allow skipping installation
    # to honor the user's request; we still require PATH setup.
    if os.path.isdir(install_dir):
        # Heuristic: if directory contains any file starting with 'uv' assume installed
        try:
            for name in os.listdir(install_dir):
                if name.lower().startswith("uv"):
                    return install_dir
        except Exception:
            pass
    return None


if __name__ == "__main__":
    try:
        install_uv()
    except subprocess.CalledProcessError as e:
        print(f"Installer failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)