import io
import re
from typing import Literal, List
import aiohttp
import gui
import discord
import asyncio
from PIL import Image, ImageDraw
from discord import app_commands
import numpy as np
from assets import GeoJSONGeometry, GeoJSONFeature
# import datetime
from utility.views import BaseView
from bot import (
    TCBot,
    TC_Cog_Mixin,
)
from discord.ext import commands
from .PalSub import read_data, write_data
CELL_SIZE=200
from discord.app_commands import Choice

def draw_grid(filepath, cell_size=200):
    with Image.open(filepath).convert("RGBA") as img:
        overlay2 = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw2 = ImageDraw.Draw(overlay2)
        cell_size = 200
        width, height = img.size
        for x in range(0, width, cell_size):
            draw2.line([(x, 0), (x, height)], fill=(255, 255, 255, 60), width=1)
        for y in range(0, height, cell_size):
            draw2.line([(0, y), (width, y)], fill=(255, 255, 255, 60), width=1)
        img = Image.alpha_composite(img, overlay2)
    return img

def highlight(img, coordinate, color=(255,0,0,200)):

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.line(
        [
            (coordinate[0] + 1.5, coordinate[1] - 1),
            (coordinate[0] + 1.5, coordinate[1] - 6),
        ],
        fill=color,
        width=2,
    )  # North
    draw.line(
        [
            (coordinate[0] + 0.5, coordinate[1] + 2),
            (coordinate[0] + 0.5, coordinate[1] + 7),
        ],
        fill=color,
        width=2,
    )  # South
    draw.line(
        [
            (coordinate[0] - 1, coordinate[1] + 1.5),
            (coordinate[0] - 6, coordinate[1] + 1.5),
        ],
        fill=color,
        width=2,
    )  # West
    draw.line(
        [
            (coordinate[0] + 2, coordinate[1] + 0.5),
            (coordinate[0] + 7, coordinate[1] + 0.5),
        ],
        fill=color,
        width=2,
    )  # East
    draw.ellipse(
        [
            coordinate[0] - 1,
            coordinate[1] - 1,
            coordinate[0] + 2,
            coordinate[1] + 2,
        ],
        outline=color,
        width=1,
    )
    draw.ellipse(
        [
            coordinate[0] - 4,
            coordinate[1] - 4,
            coordinate[0] + 5,
            coordinate[1] + 5,
        ],
        outline=color,
        width=1,
    )
    img = Image.alpha_composite(img, overlay)
    return img

def crop_image(image, coordinate, off_by, cell_size=200):
    ccr = coordinate
    bc = ccr + off_by + np.array((1, 1))
    uc = ccr - off_by
    left = max(uc[0] * cell_size, 0)
    top = max(uc[1] * cell_size, 0)
    right = min(bc[0] * cell_size, image.width)
    bottom = min(bc[1] * cell_size, image.height)
    cropped_img = image.crop((left, top, right, bottom))
    return cropped_img

def capitalize_first_letter(string: str) -> str:
    return string.capitalize() if string else ""


coor = app_commands.Range[int, -1000, 1000]
msize = app_commands.Range[int, 1, 20]

class GotoModal(discord.ui.Modal, title="goto"):
    def __init__(self, *args, pview=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.parent_view=pview
        

    name = discord.ui.TextInput(
        label="Enter x/y coordinates split by space or comma",
        placeholder="Enter coordinates to focus on. ",
        required=True,
        max_length=256,
    )



    async def on_submit(self, interaction: discord.Interaction):
        coor=self.name.value

        split_coor = re.split(r'[ ,]+', coor)
        if len(split_coor)!=2:
            await interaction.response.send_message("You must separate by a space or comma.")
            self.stop()
            return

        pat=re.compile(r'^-?\d+$')

        if not all(pat.match(c) for c in split_coor):
            await interaction.response.send_message("Coordinates must be integers.")
            self.stop()
            return
        split_coor = list(map(int, split_coor))
        split_coor = [max(min(int(c), 1000), -1000) for c in split_coor]
        await interaction.response.defer()
        await self.parent_view.highlight_points(interaction,split_coor)        


    async def on_timeout(self) -> None:
        self.stop()

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        return await super().on_error(interaction, error)

class MapViewer(BaseView):
    """
    scrollable palworld map.
    """

    def __init__(
        self,
        *,
        user,
        timeout=30 * 15,
        img=None,
        initial_coor=None,
    ):
        super().__init__(user=user, timeout=timeout)
        self.value = False
        self.done = None
        self.img=img
        self.focus_cell = np.array(initial_coor)//CELL_SIZE

    async def highlight_points(self,interaction:discord.Integration,coor):
        x2 = coor[0] + 1000
        y2 = 1000 - coor[1]
        coordinate=(x2 * 2, y2 * 2)
        self.img=highlight(self.img,coordinate)
        self.focus_cell = np.array(coordinate)//CELL_SIZE
        embed,file=self.make_embed()
        
        await interaction.edit_original_response(content='',embed=embed, attachments=[file])


    def make_embed(self):
        coors=f"Viewing cell {self.focus_cell[0]}, {self.focus_cell[1]}"
        embed = discord.Embed(
            description=f"Current pal map view.  \n{coors}"[:4000],
            timestamp=discord.utils.utcnow(),
        )
        

        cropped_img=crop_image(self.img,self.focus_cell,off_by=np.array((2,1)))
        with io.BytesIO() as image_binary:
            cropped_img.save(image_binary, "PNG")
            image_binary.seek(0)
            file = discord.File(fp=image_binary, filename="highlighted_palmap.png")

        
        embed.set_image(url="attachment://highlighted_palmap.png")
        embed.set_thumbnail(url="https://i.imgur.com/33AfdFE.png")

        return embed, file

    async def on_timeout(self) -> None:
        self.value = "timeout"
        self.stop()

    @discord.ui.button(label="Up", style=discord.ButtonStyle.green, row=2)
    async def move_up(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.focus_cell+=np.array((0,-1))
        #await interaction.response.defer()
        embed, file=self.make_embed()
        await interaction.response.edit_message(content='',embed=embed, attachments=[file])


    @discord.ui.button(label="Down", style=discord.ButtonStyle.green, row=4)
    async def move_down(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.focus_cell+=np.array((0,1))
        #await interaction.response.defer()
        embed, file=self.make_embed()
        await interaction.response.edit_message(content='',embed=embed, attachments=[file])

    @discord.ui.button(label="Left", style=discord.ButtonStyle.green, row=3)
    async def move_left(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.focus_cell+=np.array((-1,0))
        #await interaction.response.defer()
        embed, file=self.make_embed()

        await interaction.response.edit_message(content='',embed=embed, attachments=[file])

    @discord.ui.button(label="Right", style=discord.ButtonStyle.green, row=3)
    async def move_right(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.focus_cell+=np.array((1,0))
        #await interaction.response.defer()
        embed, file=self.make_embed()

        await interaction.response.edit_message(content='',embed=embed, attachments=[file])

    @discord.ui.button(label="GoTo", style=discord.ButtonStyle.green, row=4)
    async def gotocoor(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(GotoModal(pview=self,timeout=60*10))

        #await interaction.edit_original_response(content='',embed=embed, attachments=[file])

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.edit_message(content="Terminating.")
        self.stop()


class PalworldAPI(commands.Cog, TC_Cog_Mixin):
    """A palworld cog.  work in progress."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        self.locations:List[GeoJSONFeature]=read_data()
        # self.session=aiohttp.ClientSession()

    def cog_unload(self):
        pass
        # Remove the task function.

    @app_commands.command(name="get_pal", description="get a single pal.")
    @app_commands.describe(pal_name="name of pal to retrieve info for.")
    async def palget(self, interaction: discord.Interaction, pal_name: str):
        """Experimental palworld API wrapper."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        # Convert the timestamp string to a datetime object
        async with aiohttp.ClientSession() as session:
            _data_call = await session.get(
                f"https://api.palshome.org/v1/data/{pal_name}",
                headers={"api-key": self.bot.keys.get("palapi", None)},
            )  # Let's gather our data about the provided Pal from the endpoint.
            if (
                _data_call.status != 200
            ):  # If the API response returns no data, let's stop the command execution here and send a message.
                return await ctx.send(
                    "I'm sorry but i couldn't find the Pal you're looking for, check for any typo or error and try again"
                )

            # Otherwise let's continue with our data now being here.
            _data = await _data_call.json()  # We convert the response into JSON.
            print(_data)
        # Now you're free to do anything you want with the Pal data!
        pal_data = _data
        stats = pal_data["extras"]["stats"]
        # Add fields for stats
        stats = pal_data["extras"]["stats"]
        catchable = "Catchable." if pal_data["is_catchable"] is True else ""
        boss = "Can appear as boss." if pal_data["is_boss"] is True else ""
        desc = f"{pal_data['description']}\n  `Walk:{stats['walk_speed']},Run:{stats['run_speed']},RideSprint:{stats['ride_sprint_speed']},Hunger:{pal_data['extras']['hunger']}`"
        embed = discord.Embed(
            title=f"Pal Name: {pal_data['pal_name']}",
            description=desc,
            color=discord.Color.green(),  # You can change the color as per your preference
        )

        embed.set_thumbnail(url=pal_data["image"])
        elements = ",".join(ele for ele in pal_data["elements"])
        embed.set_author(name=f"Paldex no {pal_data['paldex_position']}.  {elements}")
        # Add fields for basic information

        embed.add_field(
            name="Stats",
            value=f"`HP:` {stats['hp']}\n`MeleeAttack:` {stats['meele_attack']}\n `RangedAttack`: {stats['shot_attack']}\n`Defense:` {stats['defense']}\n`Support:` {stats['support']}",
            inline=True,
        )

        works = "\n".join(
            [f"{i.capitalize()}: {work}" for i, work in pal_data["works"].items()]
        )
        embed.add_field(name="Works", value=f"{works}", inline=True)

        # Add skills
        skills = pal_data["extras"]["skills"]
        active_skills = skills["active"]
        skills_str = "\n".join(
            [
                f"Lvl.{skill['unlocks_at_level']}:**{skill['name']}** `POW:{skill['power']}`: {skill['element']} \n{skill['description']}".strip()
                for skill in active_skills
            ]
        )
        embed.add_field(name="Active Skills", value=skills_str, inline=False)

        # Add partner
        if pal_data["extras"]["skills"]["partner"]:
            partner = pal_data["extras"]["skills"]["partner"]
            embed.add_field(
                name=f"Partner Skill: {partner['name']}",
                value=f"{partner['description']}",
                inline=False,
            )
        # Add passive
        if pal_data["extras"]["skills"]["passive"]:
            passive = pal_data["extras"]["skills"]["passive"]
            embed.add_field(
                name=f"Passive Skill: {passive['name']}",
                value=f"{passive['description']}",
                inline=False,
            )

        # Add drops
        embed.add_field(name="Drops", value=", ".join(pal_data["drops"]), inline=True)

        # Add locations
        embed.add_field(
            name="Locations",
            value=f"[Day]({pal_data['locations']['day']}) - [Night]({pal_data['locations']['night']})\n{pal_data['extras']['rarity']}",
            inline=True,
        )
        embed.add_field(name="Size", value=pal_data["extras"]["size"], inline=True)

        embed.set_footer(text=f"{catchable}{boss}  Price:{stats['price_market']}")
        # Finally we send it to the channel where the command has been used!
        return await ctx.send(embed=embed)

    @app_commands.command(name="palmap", description="get the palworld map.")
    @app_commands.describe(x="X coordinate to retrieve")
    @app_commands.describe(y="Y coordinate to retrieve")
    @app_commands.describe(size="Sectors of map to view.")
    async def palmap(
        self,
        interaction: discord.Interaction,
        x: coor = 0,
        y: coor = 0,
        size: msize = 1,
    ):
        """Experimental palworld API wrapper."""
        ctx: commands.Context = await self.bot.get_context(interaction)
        # Convert the timestamp string to a datetime object
        mes = await ctx.send("please wait", ephemeral=True)
        file_path = "./assets/palmap2.png"
        x2 = x + 1000
        y2 = 1000 - y


        
        coordinate=(x2 * 2, y2 * 2)
        img=draw_grid(file_path)
        img=highlight(img, coordinate)
        for f in self.locations:
            xa,ya=f.geometry.get_coordinates()
            x2a = xa + 1000
            y2a = 1000 - ya
            coordinatea=(x2a * 2, y2a * 2)
            img=highlight(img,coordinatea,(0,0,255,200))
        #cropped_img = crop_image(img,np.array(coordinate)//CELL_SIZE, np.array((3, 2)))
        view=MapViewer(user=ctx.author,img=img,initial_coor=coordinate)

        emb,file=view.make_embed()
        await mes.edit(content="done", attachments=[file],embed=emb,view=view)


    @app_commands.command(name="palmap_add", description="Owner only, add a labeled point to map")
    @app_commands.describe(x="X coordinate to set")
    @app_commands.describe(y="Y coordinate to set")
    @app_commands.describe(name="name of point to add")
    @app_commands.guild_only()
    @app_commands.guilds(discord.Object(1071087693481652224),discord.Object(1077964401849667655))
    @app_commands.describe(pointtype="add a point to map")
    async def palmapadd(
        self,
        interaction: discord.Interaction,
        x: coor,
        y: coor,
        name: str,
        pointtype: Literal['eagle','tower','item_merchant','pal_merchant','black_market', 'effigy', 'dungeon']

    ):
        ctx: commands.Context = await self.bot.get_context(interaction)
        if interaction.user != self.bot.application.owner:
            await ctx.send("This command is owner only, buddy.")
            return
        point_geometry = GeoJSONGeometry.init_sub("Point", [x, y])
        point_properties = {"name": name, 'pointtype':pointtype}
        point_feature = GeoJSONFeature(geometry=point_geometry, properties=point_properties)
        for pf in self.locations:
            if pf==point_feature:
                await ctx.send("Point is already present.")
                return
        self.locations.append(point_feature)
        write_data(self.locations)
        # Convert the timestamp string to a datetime object
        mes = await ctx.send("please wait", ephemeral=True)

        await mes.edit(content="done")



async def setup(bot):

    await bot.add_cog(PalworldAPI(bot))


async def teardown(bot):

    await bot.remove_cog("PalworldAPI")
