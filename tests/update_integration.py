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


async def check_ha_available(timeout: int = 10) -> bool:
    """Check if Home Assistant is available."""
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{HA_URL}/api/",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                return response.status == 200
    except Exception:
        return False


async def wait_for_ha(timeout: int = 120) -> bool:
    """Wait for HA to be available after restart."""
    print(f"Waiting for HA to restart (max {timeout}s)...")
    for i in range(timeout // 5):
        if await check_ha_available():
            print(f"HA is back up after {(i + 1) * 5}s")
            return True
        await asyncio.sleep(5)
    print("HA did not come back within timeout")
    return False


async def restart_ha() -> None:
    """Restart Home Assistant."""
    print("Restarting Home Assistant...")
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{HA_URL}/api/services/homeassistant/restart",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
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
                f"{HA_URL}/api/states/update.cfl_commute_update",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    state = await response.json()
                    version = state.get("attributes", {}).get("installed_version", None)
                    return (version, True)
                elif response.status == 404:
                    return (None, False)
    except Exception as e:
        print(f"Could not check states: {e}")
    return (None, False)


async def redownload_via_hacs(local_commit: str) -> bool:
    """Redownload CFL Commute via HACS API with retry logic."""
    print("Starting HACS update via API...")
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                # Trigger update via update/install service
                print(f"Attempt {attempt + 1}: Triggering update/install service...")
                payload = {"entity_id": "update.cfl_commute_update"}

                async with session.post(
                    f"{HA_URL}/api/services/update/install",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    print(f"Update response: {response.status}")

                    # If HACS returns 500, it might still be processing - check status
                    if response.status == 500:
                        print("HACS returned 500, checking update status...")
                    elif response.status not in (200, 201):
                        if attempt < 2:
                            print(f"Retrying in 5 seconds...")
                            await asyncio.sleep(5)
                            continue
                        print(f"Update failed with status {response.status}")
                        return False

                # Wait for update to complete
                print("Waiting for update to complete...")
                for i in range(90):  # Wait up to 90 seconds
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
                                        print(
                                            f"✓ Update complete! Installed: {installed}"
                                        )
                                        return True
                                    else:
                                        print(
                                            f"✗ Update in progress but failed. Installed: {installed}, Latest: {latest}"
                                        )
                                        return False
                    except Exception as e:
                        print(f"Status check error: {e}")

                    await asyncio.sleep(1)

                print("Timeout waiting for update")
                if attempt < 2:
                    print("Retrying...")
                    await asyncio.sleep(5)
                    continue
                return False

        except asyncio.TimeoutError:
            print(f"Attempt {attempt + 1} timed out")
            if attempt < 2:
                await asyncio.sleep(5)
                continue
            return False
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                await asyncio.sleep(5)
                continue
            return False

    return False


async def main():
    if not HA_TOKEN:
        print("Error: HA_TOKEN not found in .env")
        sys.exit(1)

    # Check HA is available first
    if not await check_ha_available():
        print("Error: Home Assistant is not available")
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
                print("→ Restarting Home Assistant...")
                await restart_ha()
                if await wait_for_ha():
                    print("✓ HA restarted successfully")
                else:
                    print("✗ HA restart failed or timed out")
                    print("→ Please restart HA manually if needed")
            else:
                print("✗ Redownload failed")
                print("→ Try restarting HA manually or updating via HACS UI")
                sys.exit(1)
        else:
            print(f"✓ Version up to date ({local_commit})")
            print("→ No update needed")
    else:
        print("CFL Commute not installed")
        print("→ Please install via HACS first")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
