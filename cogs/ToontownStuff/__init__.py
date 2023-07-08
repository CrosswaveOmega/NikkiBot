from .cog_embed import *
from .research_help import read_article

async def setup(bot):
    import gui
    gui.print(f"loading in child module {__name__}")

async def teardown(bot):
    import gui
    gui.print(f"unloading child module {__name__}")

