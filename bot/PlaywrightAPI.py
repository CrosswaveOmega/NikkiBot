
from playwright.async_api import async_playwright
import gui

class PlaywrightMixin:
    '''Mixin that provides rotating bot statuses.'''
    playapi=None
    browser=None
    browser_on=False
    async def start_player(self):
        gui.print("Playwright is initalizing...")
        self.playapi=await async_playwright().start()
        gui.print("Playwright initalized.")
    async def open_browser(self):
        if self.playapi==None:
            raise Exception("Still loading the website stuff!")
        if self.browser==None:
            self.browser = await self.playapi.chromium.launch()
            self.browser_on=True

    async def get_browser(self):
        if self.browser==None:
            self.browser = await self.playapi.chromium.launch()
            self.browser_on=True
        return self.browser

    async def close_browser(self):
        if self.browser!=None:
            await self.browser.close()
            self.browser_on=False
            self.browser=None