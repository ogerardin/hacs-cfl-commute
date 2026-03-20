#!/usr/bin/env python3
"""Test CFL Commute configuration flow using Playwright."""

import asyncio
import os
import socket

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()


def get_ha_ip():
    try:
        ip = socket.gethostbyname("homeassistant.local")
        return f"http://{ip}:8123"
    except:
        return "http://homeassistant.local:8123"


HA_URL = get_ha_ip()
INTEGRATION_URL = f"{HA_URL}/config/integrations/integration/cfl_commute"
HA_USERNAME = os.getenv("HA_USERNAME")
HA_PASSWORD = os.getenv("HA_PASSWORD")
CFL_API_KEY = os.getenv("CFL_API_KEY")


async def login_to_ha(page) -> bool:
    """Login to Home Assistant with username/password (OAuth flow)."""
    if not HA_USERNAME or not HA_PASSWORD:
        print("HA_USERNAME or HA_PASSWORD not set in .env")
        return False

    print(f"Logging in as {HA_USERNAME}...")

    try:
        username_input = page.locator(
            "input[name='username'], input[id='username'], input[placeholder*='user' i]"
        ).first
        if await username_input.is_visible(timeout=3000):
            await username_input.fill(HA_USERNAME)
            password_input = page.locator(
                "input[name='password'], input[id='password'], input[type='password']"
            ).first
            await password_input.fill(HA_PASSWORD)
            await page.keyboard.press("Enter")
            print("Pressed Enter to submit")

            try:
                await page.wait_for_url(
                    lambda url: "auth/authorize" not in url, timeout=15000
                )
                print("Login successful")
            except:
                print("Still on auth page - checking state...")

            return True
        else:
            print("No login form visible")
    except Exception as e:
        print(f"Login error: {e}")

    return True


async def test_setup_flow() -> bool:
    """Test the CFL Commute configuration flow."""
    print("Testing CFL Commute setup flow...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(60000)

        # Step 1: Login
        print("Step 1: Logging in...")
        await page.goto(HA_URL, wait_until="networkidle", timeout=60000)
        await login_to_ha(page)
        await asyncio.sleep(3)

        # Step 2: Find CFL Commute in integrations
        print("Step 2: Finding CFL Commute...")
        await page.goto(
            f"{HA_URL}/config/integrations", wait_until="networkidle", timeout=60000
        )
        await asyncio.sleep(5)
        await page.screenshot(path="01_integrations.png")

        try:
            cfl_link = page.locator("text=CFL").first
            if await cfl_link.is_visible(timeout=3000):
                print("✓ Found CFL Commute")
                await cfl_link.click()
                await asyncio.sleep(2)
                await page.screenshot(path="02_cfl_page.png")
        except:
            print("✗ CFL Commute not found in integrations")
            await browser.close()
            return False

        # Step 3: Start config flow
        print("Step 3: Starting config flow...")
        try:
            add_button = page.get_by_role("button", name="Add Entry").first
            if await add_button.is_visible(timeout=5000):
                await add_button.click()
                await asyncio.sleep(3)
                await page.screenshot(path="03_config_started.png")
                print("✓ Config flow started")
        except Exception as e:
            print(f"✗ Could not find Add Entry: {e}")
            await browser.close()
            return False

        # Step 4: Enter API Key
        print("Step 4: Entering API Key...")
        await page.screenshot(path="04_api_key.png")

        try:
            api_key_input = page.locator("input[type='password']").first
            if await api_key_input.is_visible(timeout=5000):
                if CFL_API_KEY:
                    await api_key_input.fill(CFL_API_KEY)
                    await page.screenshot(path="05_api_key_filled.png")
                else:
                    print("⚠ CFL_API_KEY not set in .env - skipping")

                submit_button = page.get_by_role("button", name="Submit")
                if await submit_button.is_visible():
                    await submit_button.click()
                    await asyncio.sleep(3)
                    await page.screenshot(path="06_origin_step.png")
                    print("✓ API Key submitted")
        except Exception as e:
            print(f"Step 4 error: {e}")
            await page.screenshot(path="04_error.png")

        # Step 5: Origin station selection
        print("Step 5: Origin station selection...")
        await page.screenshot(path="07_origin.png")

        try:
            station_input = page.locator("input[type='text']").first
            if await station_input.is_visible(timeout=5000):
                await station_input.fill("Luxembourg")
                await page.screenshot(path="08_origin_filled.png")

                submit_button = page.get_by_role("button", name="Submit")
                if await submit_button.is_visible():
                    await submit_button.click()
                    await asyncio.sleep(3)
                    await page.screenshot(path="09_origin_results.png")
                    print("✓ Origin station searched")
        except Exception as e:
            print(f"Step 5 error: {e}")

        await page.screenshot(path="99_complete.png")
        print("✓ Setup flow test complete")
        await browser.close()
        return True


async def main():
    print("CFL Commute Setup Flow Test")
    print("=" * 50)

    if not HA_USERNAME or not HA_PASSWORD:
        print("Error: HA_USERNAME or HA_PASSWORD not set in .env")
        return

    try:
        success = await test_setup_flow()
        if success:
            print("=" * 50)
            print("✓ Test passed")
        else:
            print("=" * 50)
            print("✗ Test failed")
    except Exception as e:
        print(f"Error: {e}")

    print("\nScreenshots saved for debugging.")


if __name__ == "__main__":
    asyncio.run(main())
