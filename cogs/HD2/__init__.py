from .embeds import campaign_view,create_assignment_embed, create_campaign_str,create_planet_embed, create_war_embed

from .hdapi import call_api

from .helldive import *

async def setup(bot):
    print(f"loading in child module {__name__}")


async def teardown(bot):
    print(f"unloading child module {__name__}")