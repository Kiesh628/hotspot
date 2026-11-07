import sys
import os
import subprocess
import requests
import logging

logger = logging.getLogger("HotspotUpdater")

REPO = "Kiesh628/hotspot"
CURRENT_VERSION = "v1.2.6"

def check_for_updates():
    """
    Checks GitHub Releases for updates on application launch.
    Uses the direct GitHub release web redirect (bypasses GitHub REST API rate limits).
    If a newer release exists and the app is running as a compiled .exe,
    downloads the binary and performs an in-place restart.
    """
    try:
        # Direct release redirect URL — never rate-limited by GitHub
        url = f"https://github.com/{REPO}/releases/latest"
        resp = requests.get(url, allow_redirects=True, timeout=5)
        if resp.status_code != 200:
            return

        # URL redirects to https://github.com/Kiesh628/hotspot/releases/tag/vX.Y.Z
        latest_tag = resp.url.rstrip("/").split("/")[-1].strip()

        # If tag is newer than CURRENT_VERSION
        if latest_tag and latest_tag != CURRENT_VERSION:
            logger.info(f"New update found: {latest_tag} (Current: {CURRENT_VERSION})")
            
            download_url = f"https://github.com/{REPO}/releases/latest/download/Hotspot.exe"
            current_exe = sys.executable

            # Only perform in-place replacement if running as compiled executable
            if not getattr(sys, "frozen", False) or not current_exe.lower().endswith(".exe"):
                logger.info(f"Running from source: update {latest_tag} available at {download_url}")
                return

            new_exe = os.path.join(os.path.dirname(current_exe), "Hotspot_new.exe")
            
            # Download new executable directly
            logger.info("Downloading latest update...")
            r = requests.get(download_url, stream=True, allow_redirects=True, timeout=60)
            if r.status_code == 200:
                with open(new_exe, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)

                # Write a detached batch script to swap files once this process exits
                batch_script = os.path.join(os.path.dirname(current_exe), "hotspot_update.bat")
                with open(batch_script, "w") as f:
                    f.write(f"""@echo off
timeout /t 1 /nobreak >nul
:retry
move /y "{new_exe}" "{current_exe}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto retry
)
start "" "{current_exe}"
del "%~f0"
exit
""")
                # DETACHED_PROCESS = 0x00000008, CREATE_NEW_PROCESS_GROUP = 0x00000200
                creation_flags = 0x00000008 | 0x00000200
                subprocess.Popen(["cmd.exe", "/c", batch_script], close_fds=True, creationflags=creation_flags)
                sys.exit(0)

    except Exception as e:
        logger.warning(f"Update check failed: {e}")
