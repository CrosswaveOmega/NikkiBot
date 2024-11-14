from .embeds import (
    campaign_view,
    create_assignment_embed,
    create_campaign_str,
    create_planet_embed,
    create_war_embed,
    campaign_text_view,
    station_embed,
)

from .db import ServerHDProfile

from .GameStatus import (
    ApiStatus,
    add_to_csv,
    load_from_json,
    save_to_json,
    write_statistics_to_csv,
)
from .image_draw import *
from .maths import maths
from .predict import predict_needed_players, make_prediction_for_eps
from .buttons import ListButtons
from .makeplanets import get_planet
from .diff_util import GameEvent


async def setup(bot):
    print(f"loading in child module {__name__}")


async def teardown(bot):
    print(f"unloading child module {__name__}")
