#!/usr/bin/env python3
"""Update CFL Commute integration via HACS.

Checks version, redownloads if needed, and restarts HA.
"""

import asyncio
import os
import subprocess
import sys
import socket

import aiohttp
from dotenv import load_dotenv

load_dotenv()


def get_ha_ip():
    try:
        ip = socket.gethostbyname("homeassistant.local")
        return f"http://{ip}:8123"
    except:
        return "http://homeassistant.local:8123"


HA_URL = get_ha_ip()
HA_TOKEN = os.getenv("HA_TOKEN")


def get_commit_hash() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    )
    return result.stdout.strip()


async def wait_for_ha(timeout: int = 120) -> bool:
    print(f"Waiting for HA to restart (max {timeout}s)...")
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}
    for i in range(timeout // 5):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{HA_URL}/api/", headers=headers) as response:
                    if response.status == 200:
                        print(f"HA is back up after {(i + 1) * 5}s")
                        return True
        except Exception:
            pass
        await asyncio.sleep(5)
    print("HA did not come back within timeout")
    return False


async def restart_ha() -> None:
    print("Restarting Home Assistant...")
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{HA_URL}/api/services/homeassistant/restart", headers=headers
            ) as response:
                print(f"Restart API response: {response.status}")
    except Exception as e:
        print(f"Restart error: {e}")


async def check_integration_version() -> tuple[str | None, bool]:
    """Check if CFL Commute is installed and get version."""
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{HA_URL}/api/states/update.cfl_commute_update", headers=headers
            ) as response:
                if response.status == 200:
                    state = await response.json()
                    version = state.get("attributes", {}).get("installed_version", None)
                    return (version, True)
    except Exception as e:
        print(f"Could not check states: {e}")

    return (None, False)


async def redownload_via_hacs(local_commit: str) -> bool:
    """Redownload CFL Commute via HACS API."""
    print("Starting HACS update via API...")
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}

    async with aiohttp.ClientSession() as session:
        # Trigger update via update/install service
        print("Triggering update/install service...")
        payload = {"entity_id": "update.cfl_commute_update"}

        async with session.post(
            f"{HA_URL}/api/services/update/install",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as response:
            print(f"Update response: {response.status}")
            if response.status != 200:
                print(f"Update failed with status {response.status}")
                return False

        # Wait for update to complete
        print("Waiting for update to complete...")
        for i in range(60):  # Wait up to 60 seconds
            try:
                async with session.get(
                    f"{HA_URL}/api/states/update.cfl_commute_update",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        state = await resp.json()
                        attrs = state.get("attributes", {})
                        in_progress = attrs.get("in_progress", False)
                        percentage = attrs.get("update_percentage")
                        installed = attrs.get("installed_version")
                        latest = attrs.get("latest_version")

                        if percentage is not None:
                            print(f"  Progress: {percentage}%")

                        if not in_progress:
                            if installed == latest:
                                print(f"✓ Update complete! Installed: {installed}")
                                return True
                            else:
                                print(
                                    f"✗ Update failed. Installed: {installed}, Latest: {latest}"
                                )
                                return False
            except Exception as e:
                print(f"Status check error: {e}")

            await asyncio.sleep(1)

        print("Timeout waiting for update")
        return False


async def main():
    if not HA_TOKEN:
        print("Error: HA_TOKEN not found in .env")
        sys.exit(1)

    local_commit = get_commit_hash()
    print(f"Local commit: {local_commit}")
    print("=" * 50)

    # Check current installed version
    version, found = await check_integration_version()

    if found:
        print(f"Installed version: {version}")
        if version != local_commit:
            print(f"Version mismatch! Local: {local_commit}, Installed: {version}")
            print("→ Redownloading...")

            # Redownload via HACS
            success = await redownload_via_hacs(local_commit)
            if success:
                print("✓ Redownload completed")

                # Restart HA
                await restart_ha()
                if await wait_for_ha():
                    print("✓ HA restarted successfully")
                else:
                    print("✗ HA restart failed")
            else:
                print("✗ Redownload failed")
        else:
            print(f"✓ Version up to date ({local_commit})")
            print("→ No update needed")
    else:
        print("CFL Commute not installed")
        print("→ Please install via HACS first")


if __name__ == "__main__":
    asyncio.run(main())
