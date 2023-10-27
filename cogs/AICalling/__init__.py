from .AI_MessageTemplates import AIMessageTemplates


async def setup(bot):
    import gui

    gui.print(f"loading in child module {__name__}")


async def teardown(bot):
    import gui

    gui.print(f"unloading child module {__name__}")
