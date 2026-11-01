import asyncio
from core.browser_agent import BrowserAgent


class BrowserTool:

    def __init__(self):
        self.agent = BrowserAgent()
        self.started = False

    async def ensure_started(self):
        if not self.started:
            await self.agent.start()
            self.started = True

    async def browse(self, urls):

        await self.ensure_started()

        results = await self.agent.open_multiple(urls)

        return results

    def run(self, urls):
        return asyncio.run(self.browse(urls))