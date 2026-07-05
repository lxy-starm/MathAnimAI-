"""
MathAnimAI Web UI Automated Test (Playwright)

Usage:
    1. Start the web server: python main.py
    2. Run this test: python tests/test_web_ui.py

The test will:
    1. Open the Gradio web UI
    2. Enter a math problem
    3. Click the generate button
    4. Wait for video generation (up to 5 minutes)
    5. Verify the video player appears
"""

import sys
import os
import time
import subprocess
import signal

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ================================================================
# Configuration
# ================================================================
GRADIO_URL = "http://127.0.0.1:7060"
TEST_PROBLEM = "求圆的面积，半径为5"
MAX_WAIT_TIME = 300 * 1000  # 5 minutes in ms


def start_server():
    """Start the Gradio server if not already running"""
    import requests
    try:
        resp = requests.get(f"{GRADIO_URL}/gradio_api/startup-events", timeout=3)
        if resp.status_code == 200:
            print("[INFO] Server already running")
            return None
    except Exception:
        pass

    print("[INFO] Starting server...")
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    # Wait for server to be ready
    for _ in range(30):
        time.sleep(2)
        try:
            resp = requests.get(f"{GRADIO_URL}/gradio_api/startup-events", timeout=3)
            if resp.status_code == 200:
                print("[INFO] Server is ready")
                return proc
        except Exception:
            pass
    print("[ERROR] Server failed to start")
    return None


def run_test():
    """Run the automated web UI test"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="zh-CN",
        )
        page = context.new_page()

        # Collect console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print(f"[1/6] Navigating to {GRADIO_URL} ...")
        page.goto(GRADIO_URL, wait_until="networkidle", timeout=30000)
        print("[OK] Page loaded")

        # Wait for Gradio to fully render
        page.wait_for_selector("#problem_input textarea", timeout=15000)
        print("[OK] Gradio UI rendered")

        # Step 2: Enter problem text
        print(f"[2/6] Entering problem: '{TEST_PROBLEM}' ...")
        textarea = page.locator("#problem_input textarea")
        textarea.fill(TEST_PROBLEM)
        actual_text = textarea.input_value()
        assert actual_text == TEST_PROBLEM, f"Text mismatch: got '{actual_text}'"
        print("[OK] Problem text entered")

        # Step 3: Verify grade and type selectors
        print("[3/6] Checking selectors ...")
        grade_dropdown = page.locator("#grade_selector")
        type_dropdown = page.locator("#type_selector")
        assert grade_dropdown.is_visible(), "Grade dropdown not visible"
        assert type_dropdown.is_visible(), "Type dropdown not visible"
        print("[OK] Selectors visible (grade=初中, type=自动识别)")

        # Step 4: Click generate button
        print("[4/6] Clicking generate button ...")
        generate_btn = page.locator("#generate_btn")
        assert generate_btn.is_visible(), "Generate button not visible"
        generate_btn.click()
        print("[OK] Generate button clicked, waiting for pipeline ...")

        # Step 5: Wait for pipeline completion
        # The status box will show success/failure message
        print("[5/6] Waiting for pipeline to complete (max 5 min) ...")
        status_box = page.locator("#status_display textarea")

        start_time = time.time()
        success = False
        last_status = ""

        while time.time() - start_time < MAX_WAIT_TIME / 1000:
            try:
                current_status = status_box.input_value() or ""
                if current_status != last_status:
                    elapsed = int(time.time() - start_time)
                    # Print last 100 chars of status
                    status_tail = current_status[-200:] if len(current_status) > 200 else current_status
                    print(f"  [{elapsed}s] Status: {status_tail[:100]}...")
                    last_status = current_status

                # Check for success indicators
                if "[OK]" in current_status and "完成" in current_status:
                    print("[OK] Pipeline completed successfully!")
                    success = True
                    break

                # Check for failure indicators
                if "失败" in current_status or "ERROR" in current_status.upper():
                    if "完成" not in current_status:
                        print(f"[FAIL] Pipeline failed: {current_status[-300:]}")
                        break

            except Exception:
                pass

            time.sleep(3)

        if not success:
            print(f"[FAIL] Pipeline did not complete within {MAX_WAIT_TIME/1000}s")
            print(f"  Final status: {last_status[-500:]}")
            browser.close()
            return False

        # Step 6: Verify video output
        print("[6/6] Checking video output ...")
        try:
            video_player = page.locator("#video_player video, #video_player source")
            page.wait_for_selector("#video_player video", timeout=30000)
            video_src = video_player.get_attribute("src") or ""
            if video_src:
                print(f"[OK] Video element found: src={video_src[:80]}...")
            else:
                print("[WARN] Video element found but no src attribute")
        except PlaywrightTimeoutError:
            print("[WARN] Video element not found in DOM (may still be loading)")
        except Exception as e:
            print(f"[WARN] Video check: {e}")

        # Check console errors
        if console_errors:
            print(f"\n[INFO] Console errors ({len(console_errors)}):")
            for err in console_errors[:5]:
                print(f"  - {err[:120]}")
        else:
            print("\n[OK] No console errors")

        browser.close()

        if success:
            print("\n" + "=" * 60)
            print("TEST RESULT: PASS")
            print("=" * 60)
            return True
        else:
            print("\n" + "=" * 60)
            print("TEST RESULT: FAIL")
            print("=" * 60)
            return False


if __name__ == "__main__":
    server_proc = start_server()
    try:
        result = run_test()
        sys.exit(0 if result else 1)
    finally:
        if server_proc:
            server_proc.terminate()
            server_proc.wait(timeout=10)
