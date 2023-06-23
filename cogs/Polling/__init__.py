from .PollingTables import PollTable, PollData, PollMessages, PollChannelSubscribe
from .PollEditViews import PollEdit
from .messtemplate import PollMessageTemplates as MessageTemplates
from .PollViews import Persistent_Poll_View

async def setup(bot):
    import gui
    gui.print(f"loading in child module {__name__}")

async def teardown(bot):
    import gui
    gui.print(f"unloading child module {__name__}")

