from .tools import *
from gptmod.chromatools import ChromaTools
from .views import *
from .LinkLoader import SourceLinkLoader
from .research_ctx import ResearchContext
from .actions import *


async def setup(bot):
    import gui

    gui.print(f"loading in child module {__name__}")


async def teardown(bot):
    import gui

    gui.print(f"unloading child module {__name__}")
