import sys
import os
import subprocess
import requests
import logging

logger = logging.getLogger("HotspotUpdater")

REPO = "Kiesh628/hotspot"
CURRENT_VERSION = "v1.1.0"

def check_for_updates():
    """
    Checks GitHub Releases for updates on application launch.
    If a newer release exists and the app is running as a compiled .exe,
    downloads the binary and performs an in-place restart.
    """
    try:
        url = f"https://api.github.com/repos/{REPO}/releases/latest"
        resp = requests.get(url, timeout=3)
        if resp.status_code != 200:
            return

        data = resp.json()
        latest_tag = data.get("tag_name", "").strip()

        # If tag is newer than CURRENT_VERSION
        if latest_tag and latest_tag != CURRENT_VERSION:
            logger.info(f"New update found: {latest_tag} (Current: {CURRENT_VERSION})")
            
            # Find Hotspot.exe asset
            download_url = None
            for asset in data.get("assets", []):
                if asset.get("name") == "Hotspot.exe":
                    download_url = asset.get("browser_download_url")
                    break

            if not download_url:
                return

            current_exe = sys.executable
            # Only perform in-place replacement if running as compiled executable
            if not getattr(sys, "frozen", False) or not current_exe.lower().endswith(".exe"):
                logger.info(f"Running from source: update {latest_tag} available at {download_url}")
                return

            new_exe = os.path.join(os.path.dirname(current_exe), "Hotspot_new.exe")
            
            # Download new executable
            logger.info("Downloading latest update...")
            r = requests.get(download_url, stream=True, timeout=30)
            if r.status_code == 200:
                with open(new_exe, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)

                # Write a temporary handoff script to swap files and restart
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
                # Launch updater batch script detached and exit current process
                subprocess.Popen(["cmd.exe", "/c", batch_script], close_fds=True)
                sys.exit(0)

    except Exception as e:
        logger.warning(f"Update check failed: {e}")
