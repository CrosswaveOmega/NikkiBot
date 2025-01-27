import csv
import datetime
import os
import re

import discord
from discord import app_commands
from discord.ext import commands
from gptfunctionutil import (
    AILibFunction,
    LibParam,
)
import cogs.HD2 as hd2
import hd2api
from discord.app_commands import Choice

# import datetime
from bot import (
    TC_Cog_Mixin,
    TCBot,
)
from typing import *
from utility import load_json_with_substitutions
from utility.globalfunctions import seconds_to_time_string

mode = Literal["health", "lib"]

calculation_modes = [  # param name
    Choice(name="Raw Planetary Health/damage per second", value="health"),
    Choice(name="Planetary Liberation/liberation per hour", value="lib"),
]


def extract_embed_text(embed):
    """
    Extracts the text from an embed object and formats it as a bullet list.

    Args:
        embed (Embed): The embed object to extract text from.

    Returns:
        str: A string containing the title, description, and fields of the embed, formatted as a bullet list.
    """
    bullet_list = []

    # Extract title, description, and fields from the Embed
    if embed.title:
        bullet_list.append(f"{embed.title}")

    if embed.description:
        bullet_list.append(f"{embed.description}")

    for field in embed.fields:
        bullet_list.append(f"**{field.name}**: {field.value}")

    # Join the extracted text with bullet points
    bullet_string = "\n".join([f"• {line}" for line in bullet_list])
    return bullet_string


class HelldiversMathCog(commands.Cog, TC_Cog_Mixin):
    """Cog for helldivers 2.  Consider it my embedded automaton spy."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        self.hd2 = load_json_with_substitutions("./assets/json", "flavor.json", {}).get(
            "hd2", {}
        )

    def cog_unload(self):
        pass

    @property
    def apistatus(self) -> hd2.ApiStatus:
        return self.bot.get_cog("HelldiversCog").apistatus

    async def campaign_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        """
        Autocomplete for planet lookup.  Search by either the name or index.
        """
        items = (l.get_first().planet for l in self.apistatus.campaigns.values())
        search_val = current.lower()
        results = []
        for v in items:
            if len(results) >= 25:
                break
            if search_val in v.get_name(False).lower():
                results.append(
                    app_commands.Choice(name=v.get_name(False), value=int(v.index))
                )
        return results

    calc = app_commands.Group(name="hd2_calc", description="Commands for mathdiving.")

    @calc.command(
        name="players_for_dps",
        description="estimate players needed to get a target dps on a specific planet",
    )
    @app_commands.autocomplete(byplanet=campaign_autocomplete)
    @app_commands.describe(dps="damage per second")
    async def players_for_dps(
        self, interaction: discord.Interaction, dps: float, byplanet: int
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)

        embeds = []
        mp_mult = self.apistatus.war.get_first().impactMultiplier
        if byplanet in self.apistatus.planets:
            planet = self.apistatus.planets[byplanet]
            eps = hd2.maths.dps_to_eps(dps, planet.regenPerSecond, mp_mult)
            play, conf = hd2.predict_needed_players(eps, mp_mult)
            embeds.append(
                hd2.create_planet_embed(
                    planet, cstr=None, last=None, stat=self.apistatus
                )
            )
            await ctx.send(
                f"Need `{play}` players to achieve dps of `{dps}` on {planet.get_name()}."
                + f"\n standard error `{conf}`.",
                ephemeral=True,
            )
            # await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)
        else:
            await ctx.send("Planet not found.", ephemeral=True)

    @calc.command(
        name="players_for_lph",
        description="estimate players needed to get a target lph on a specific planet",
    )
    @app_commands.autocomplete(byplanet=campaign_autocomplete)
    @app_commands.describe(lph="liberation percent per hour")
    async def players_for_lph(
        self, interaction: discord.Interaction, lph: float, byplanet: int
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)

        embeds = []
        mp_mult = self.apistatus.war.get_first().impactMultiplier
        if byplanet in self.apistatus.planets:
            planet = self.apistatus.planets[byplanet]
            dps = hd2.maths.lph_to_dps(lph, planet.maxHealth)
            eps = hd2.maths.dps_to_eps(dps, planet.regenPerSecond, mp_mult)
            play, conf = hd2.predict_needed_players(eps, mp_mult)
            embeds.append(
                hd2.create_planet_embed(
                    planet, cstr=None, last=None, stat=self.apistatus
                )
            )
            await ctx.send(
                f"Need `{play}` players to achieve lph of `{lph}({dps} dps)` on {planet.get_name()}."
                + f"\n standard error `{conf}`.",
                ephemeral=True,
            )
            # await pages_of_embeds(ctx, embeds, show_page_nums=False, ephemeral=False)
        else:
            await ctx.send("Planet not found.", ephemeral=True)

    @calc.command(
        name="dps_for_players",
        description="estimate average dps preformed by X players",
    )
    @app_commands.describe(players="number of players")
    async def dps_for_players(self, interaction: discord.Interaction, players: float):
        ctx: commands.Context = await self.bot.get_context(interaction)
        mp_mult = self.apistatus.war.get_first().impactMultiplier

        eps, conf = hd2.predict_eps_for_players(players, mp_mult)
        dps = eps * mp_mult

        await ctx.send(
            f"`{players}` players can achieve dps of `({dps} dps)` with the current impact multiplier."
            + f"\n standard error `{conf}`.",
            ephemeral=True,
        )

    @calc.command(
        name="dps_to_lph",
        description="Convert damage per second to liberation per hour.",
    )
    @app_commands.describe(dps="damage per second")
    @app_commands.describe(max_health="Max health of the planet or event.")
    async def dps_to_lph(
        self, interaction: discord.Interaction, dps: float, max_health: int
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)
        lps = hd2.maths.dps_to_lph(dps, max_health)
        await ctx.send(
            f"`{dps}` dps is about `{lps}` liberation per hour.", ephemeral=True
        )

    @calc.command(
        name="eps_to_dps",
        description="Convert experience per second to damage per second.",
    )
    @app_commands.describe(eps="experience per second")
    async def eps_to_dps(self, interaction: discord.Interaction, eps: float):
        ctx: commands.Context = await self.bot.get_context(interaction)
        war = self.apistatus.war.get_first()
        dps = war.impactMultiplier * eps
        lps = hd2.maths.dps_to_lph(dps, 1000000)
        await ctx.send(
            f"`{eps}` dps is about `{dps}` dps per second, and `{lps}` liberation per hour.",
            ephemeral=True,
        )

    @calc.command(
        name="estimate_target_dps",
        description="Estimate the target dps(or lph) given the target hp, seconds/hours, and decay",
    )
    @app_commands.describe(hp="target planetary hp")
    @app_commands.describe(timev="target planetary hp")
    @app_commands.describe(regenrate="Decay rate in dps or lph")
    @app_commands.choices(
        mode=[
            Choice(name="Raw Planetary Health/damage per second", value="health"),
            Choice(name="Planetary Liberation/liberation per hour", value="lib"),
        ]
    )
    async def estimate_target_dps(
        self,
        interaction: discord.Interaction,
        hp: float,
        timev: float,
        regenrate: float,
        mode: mode,
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)
        dps = hd2.maths.dps_for_time(hp, timev, regenrate)
        if mode == "health":
            await ctx.send(
                f"For hp`{hp}` in `{timev}` seconds, the target dps must be `{dps}`.",
                ephemeral=True,
            )
        else:
            await ctx.send(
                f"For lib `{hp}` in `{timev}` hours, the target capture rate must be `{dps}`.",
                ephemeral=True,
            )

    @calc.command(
        name="gametime",
        description="get the current game time",
    )
    async def get_startTime(
        self,
        interaction: discord.Interaction,
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)
        current_date_time = hd2api.builders.get_time_dh(self.apistatus.warall)
        await ctx.send(
            f"{discord.utils.format_dt(current_date_time,'F')}, in iso={current_date_time.isoformat()}"
        )

    @calc.command(
        name="get_graph",
        description="get the estimated influence to players graph",
    )
    async def get_graph(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.send_message(
            file=discord.File("saveData/graph1.png"), ephemeral=True
        )

    @calc.command(
        name="get_planet_liberation",
        description="get the planet liberation data gathered from the past 48 hours",
    )
    async def get_lib(
        self,
        interaction: discord.Interaction,
    ):
        file_path = "saveData/outs.jsonl"
        file_size = os.path.getsize(file_path)
        if file_size < 25 * 1024 * 1024:
            await interaction.response.send_message(
                file=discord.File(file_path), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "The file is too large to be sent.", ephemeral=True
            )

    @calc.command(
        name="impactdatacollection",
        description="Convert experience per second to damage per second.",
    )
    @app_commands.describe(imp="squad impact")
    @app_commands.describe(samples="total number of samples collected")
    @app_commands.describe(xp="mission xp total")
    @app_commands.describe(deaths="total number of deaths")
    @app_commands.describe(diff="mission difficulty")
    async def impactdc(
        self,
        interaction: discord.Interaction,
        imp: float,
        samples: int,
        xp: float,
        deaths: float,
        diff: int = 0,
    ):
        ctx: commands.Context = await self.bot.get_context(interaction)
        war = await self.apistatus.get_war_now()
        influence = war.impactMultiplier * imp
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        timestamp = int(now.timestamp())
        await ctx.send(
            f"`{imp}` impact (influence `{influence}` at mp_mult `{war.impactMultiplier}`), difficulty `{diff}`, `{samples}` samples,`{xp}` xp, `{deaths}` deaths. ",
            ephemeral=False,
        )
        row = {
            "timestamp": timestamp,
            "mp_mult": war.impactMultiplier,
            "impact": imp,
            "influence": influence,
            "samples": samples,
            "xp": xp,
            "diff": diff,
        }
        with open("sample_impact.csv", mode="a", newline="", encoding="utf8") as file:
            writer = csv.DictWriter(file, fieldnames=row.keys())

            # If the file is empty, write the header
            if file.tell() == 0:
                writer.writeheader()

            writer.writerow(row)

    @AILibFunction(
        name="galactic_war_status",
        description="Get the current state of the galactic war",
        enabled=True,
        force_words=["galactic war"],
        required=["comment"],
    )
    @LibParam(
        comment="An interesting, amusing remark.",
    )
    @commands.command(
        name="galactic_war_status",
        description="Get the current state of the galactic war",
        extras={},
    )
    async def get_gwar_state(
        self,
        ctx: commands.Context,
        comment: str = "Ok",
    ):
        emb = hd2.campaign_text_view(self.apistatus, self.hd2, show_stalemate=False)

        embs = []
        embs.append(emb)
        if self.apistatus.assignments:
            for i, assignment in self.apistatus.assignments.items():
                b, a = assignment.get_first_change()
                embed = hd2.create_assignment_embed(
                    b, b - a, planets=self.apistatus.planets
                )
                embs.insert(
                    0,
                    extract_embed_text(embed),
                )
        now = discord.utils.utcnow()
        out = f"Current Date: {discord.utils.utcnow().isoformat()}"

        status_emoji = {
            "<:checkboxon:1199756987471241346>": "onc",
            "<:checkboxoff:1199756988410777610>": "noc",
            "<:checkboxempty:1199756989887172639>": "emptyc",
            "<:edit:1199769314929164319>": "edit",
            "<:add:1199770854112890890>": "add",
            "<:bots:1241748819620659332>": "Automaton control ",
            "<:bugs:1241748834632208395>": "Terminid control ",
            "<:superearth:1275126046869557361>": "Human controlled ",
            "<:squid:1274752443246448702>": "Illuminate controlled ",
            "<:hdi:1240695940965339136>": "Players on",
            "<:Medal:1241748215087235143>": "medal",
            "<:rec:1274481505611288639>": "req",
            "<:supercredit:1274728715175067681>": "credits",
        }

        for em in embs:
            outv = em

            outv = re.sub(
                r"<t:(\d+):[^>]+>",
                lambda m: seconds_to_time_string(
                    (
                        datetime.datetime.fromtimestamp(
                            int(m.group(1)), tz=datetime.timezone.utc
                        )
                        - discord.utils.utcnow()
                    ).total_seconds()
                ),
                outv,
            )
            print(f"EMB={outv}")
            for e, m in status_emoji.items():
                if e in outv:
                    outv = outv.replace(e, m)
            out += outv

        print(out)
        return out

    @commands.command(
        name="galactic_war_text",
        description="Get the current state of the galactic war in text format",
        extras={},
    )
    async def get_gwar_state_text(
        self,
        ctx: commands.Context,
    ):
        text = await self.get_gwar_state(ctx, "OK.")
        embed = discord.Embed(description=text[:4096])
        await ctx.send(embed=embed)


@app_commands.allowed_installs(guilds=False, users=True)
class HD2Local(
    app_commands.Group, name="hd2local", description="Helldivers Shortcut Commands"
):
    """Stub class"""


class HelldiversGlobalCog(commands.Cog, TC_Cog_Mixin):
    """Cog for helldivers 2.  Consider it my embedded automaton spy."""

    def __init__(self, bot):
        self.bot: TCBot = bot

        self.globalonly = True
        self.hd2 = load_json_with_substitutions("./assets/json", "flavor.json", {}).get(
            "hd2", {}
        )
        # self.session=aiohttp.ClientSession()

    @property
    def apistatus(self) -> hd2.ApiStatus:
        return self.bot.get_cog("HelldiversCog").apistatus

    hd2user = HD2Local()

    @hd2user.command(
        name="get_overview", description="get the current game state from helldivers2"
    )
    async def get_overview(self, interaction: discord.Interaction) -> None:
        ctx: commands.Context = await self.bot.get_context(interaction)
        here = ""
        if self.apistatus.assignments:
            for i, assignment in self.apistatus.assignments.items():
                b, a = assignment.get_first_change()
                here = b.to_str()
        use = {"galactic_overview": {"value": [here]}}

        emb = hd2.campaign_view(self.apistatus, self.hd2)
        await ctx.send(embeds=emb, ephemeral=True)


async def setup(bot):
    module_name = "cogs.HD2Math"
    HelldiversGlobalCog
    await bot.add_cog(HelldiversMathCog(bot))
    await bot.add_cog(HelldiversGlobalCog(bot))


async def teardown(bot):
    await bot.remove_cog("HelldiversMathCog")

    await bot.remove_cog("HelldiversGlobalCog")
