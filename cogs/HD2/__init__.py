from .embeds import (
    campaign_view,
    create_assignment_embed,
    create_campaign_str,
    create_planet_embed,
    create_war_embed,
)

from .hdapi import call_api
from .db import ServerHDProfile
from .helldive import *
from .GameStatus import ApiStatus, add_to_csv, load_from_json, save_to_json
from .image_draw import *
from .maths import maths
from .predict import predict_needed_players, make_prediction_for_eps

async def setup(bot):
    print(f"loading in child module {__name__}")


async def teardown(bot):
    print(f"unloading child module {__name__}")
