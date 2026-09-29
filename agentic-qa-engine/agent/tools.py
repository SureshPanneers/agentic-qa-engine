"""Playwright-backed tools exposed to the LangChain agent.

Uses Playwright's async API so every browser call runs on the same asyncio
event loop that drives the LangGraph agent. The sync API is not safe here:
LangGraph can invoke tools from a context that isn't the exact OS thread that
started the sync Playwright driver, which raises greenlet thread-affinity
errors.
"""
import os
import time
from pathlib import Path
from typing import Optional

from langchain.tools import tool
from playwright.async_api import async_playwright, Page, Browser, Playwright

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


class BrowserSession:
    """Holds the single Playwright browser/page instance used by all tools."""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.execution_log: list[dict] = []
        self._step_counter = 0

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page(viewport={"width": 1366, "height": 768})
        await self._log("launch_browser", "pass", "Browser launched")

    async def stop(self) -> None:
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.page = None

    async def _screenshot(self, label: str) -> Optional[str]:
        if self.page is None:
            return None
        self._step_counter += 1
        safe_label = "".join(c if c.isalnum() else "_" for c in label)[:40]
        filename = f"{self._step_counter:02d}_{safe_label}.png"
        path = SCREENSHOTS_DIR / filename
        await self.page.screenshot(path=str(path))
        return str(path)

    async def _log(self, step: str, status: str, message: str) -> None:
        self.execution_log.append({
            "step": step,
            "status": status,
            "message": message,
            "screenshot": await self._screenshot(step),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        })


session = BrowserSession(headless=os.getenv("HEADLESS", "false").lower() == "true")


async def _safe(step_name: str, coro) -> str:
    """Await a coroutine, logging and reporting failure instead of raising."""
    try:
        await coro
        await session._log(step_name, "pass", f"{step_name} succeeded")
        return f"OK: {step_name} succeeded."
    except Exception as exc:
        await session._log(step_name, "fail", str(exc))
        return f"ERROR: {step_name} failed: {exc}"


@tool
async def open_browser() -> str:
    """Launch the browser. Call this once at the start of every test run."""
    if session.page is None:
        await session.start()
        return "Browser launched."
    return "Browser already running."


@tool
async def navigate(url: str) -> str:
    """Navigate the browser to the given URL."""
    if session.page is None:
        await session._log(f"navigate to {url}", "fail", "browser is not open")
        return "ERROR: browser is not open. Call open_browser first."
    return await _safe(f"navigate to {url}", session.page.goto(url))


@tool
async def click(selector: str) -> str:
    """Click an element identified by a Playwright locator string
    (CSS selector, 'text=Label', 'role=button[name=Submit]', etc.)."""
    if session.page is None:
        await session._log(f"click {selector}", "fail", "browser is not open")
        return "ERROR: browser is not open. Call open_browser first."
    return await _safe(f"click {selector}", session.page.locator(selector).first.click())


@tool
async def fill_text(selector: str, text: str) -> str:
    """Type text into an input field identified by a Playwright locator string."""
    if session.page is None:
        await session._log(f"fill {selector}", "fail", "browser is not open")
        return "ERROR: browser is not open. Call open_browser first."
    return await _safe(f"fill {selector}", session.page.locator(selector).first.fill(text))


@tool
async def get_text(selector: str) -> str:
    """Read and return the visible text content of an element, used to validate outcomes."""
    if session.page is None:
        await session._log(f"read {selector}", "fail", "browser is not open")
        return "ERROR: browser is not open. Call open_browser first."
    try:
        content = await session.page.locator(selector).first.inner_text()
        await session._log(f"read {selector}", "pass", content)
        return content
    except Exception as exc:
        await session._log(f"read {selector}", "fail", str(exc))
        return f"ERROR: could not read {selector}: {exc}"


@tool
async def assert_text_visible(text: str) -> str:
    """Verify that the given text is visible somewhere on the current page."""
    if session.page is None:
        await session._log(f"assert '{text}' visible", "fail", "browser is not open")
        return "ERROR: browser is not open. Call open_browser first."
    try:
        visible = await session.page.get_by_text(text).first.is_visible()
        status = "pass" if visible else "fail"
        await session._log(f"assert '{text}' visible", status, f"visible={visible}")
        return "OK: text is visible" if visible else "FAIL: text not found"
    except Exception as exc:
        await session._log(f"assert '{text}' visible", "fail", str(exc))
        return f"ERROR: {exc}"


@tool
async def close_browser() -> str:
    """Close the browser. Call this once as the final step of every test run."""
    await session.stop()
    return "Browser closed."


ALL_TOOLS = [open_browser, navigate, click, fill_text, get_text, assert_text_visible, close_browser]
