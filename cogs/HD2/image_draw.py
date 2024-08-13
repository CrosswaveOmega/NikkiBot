import io
import math
import os
import json
import discord
from PIL import Image, ImageDraw, ImageFont, ImageSequence
import numpy as np
from .GameStatus import ApiStatus
from .helldive import Planet
from .makeplanets import get_planet

import importlib.util


from utility.views import BaseView
from utility.image_functions import draw_arrow, draw_dot

SCALE = 1.2
CELL_SIZE = 200
GRIDDRAW = False


def update_lastval_file(lastplanets):
    lastval_file = "./saveData/lastval.json"

    lastplanets_str = json.dumps(lastplanets, sort_keys=True)

    # Load existing lastval JSON string or initialize empty
    try:
        with open(lastval_file, "r") as f:
            lastval_str = f.read().strip()
    except IOError:
        lastval_str = ""

    # Compare JSON strings and update file if necessary
    if lastplanets_str != lastval_str:
        with open(lastval_file, "w") as f:
            f.write(lastplanets_str)
        return True  # Updated
    else:
        return False  # Not updated


def draw_grid(filepath, cell_size=200):
    with Image.open(filepath).convert("RGBA") as img:
        img = img.resize((int(img.width * SCALE), int(img.height * SCALE)))

        overlay2 = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw2 = ImageDraw.Draw(overlay2)
        cell_size = int(CELL_SIZE * SCALE)
        if GRIDDRAW:
            width, height = img.size
            for x in range(0, width, cell_size):
                draw2.line([(x, 0), (x, height)], fill=(255, 255, 255, 60), width=1)
            for y in range(0, height, cell_size):
                draw2.line([(0, y), (width, y)], fill=(255, 255, 255, 60), width=1)
        img = Image.alpha_composite(img, overlay2)
    return img


def get_im_coordinates(x, y, scale=1):

    coordinate = int(round(x * 1000.0 * SCALE + 1000 * SCALE, 0)), int(
        round(1000 * SCALE - y * 1000.0 * SCALE, 1)
    )
    coordinate = coordinate[0] * scale, coordinate[1] * scale
    return coordinate


def draw_supply_lines(img, color=(0, 255, 0, 255), apistat: ApiStatus = None):
    width, height = img.size
    overlay = Image.new("RGBA", (width * 2, height * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for index, planet in apistat.planets.items():
        gpos = planet.position
        x, y = get_im_coordinates(gpos.x, gpos.y, 2)
        waypoints = planet.waypoints
        for ind in waypoints:
            target = apistat.planets[ind]
            tgpos = target.position
            tx, ty = get_im_coordinates(tgpos.x, tgpos.y, 2)
            draw.line(
                [(x, y), (tx, ty)],
                fill=color,
                width=4,
            )

        for index, planet in apistat.planets.items():
            draw_attack_lines(draw, planet, apistat)

    overlay = overlay.resize((overlay.width // 2, overlay.height // 2))

    img = Image.alpha_composite(img, overlay)
    return img


def draw_attack_lines(draw, planet, apistat: ApiStatus):

    waypoints = planet.attacking
    gpos = planet.position
    x, y = get_im_coordinates(gpos.x, gpos.y, 2)
    for ind in waypoints:
        target = apistat.planets[ind]
        tgpos = target.position
        tx, ty = get_im_coordinates(tgpos.x, tgpos.y, 2)

        draw_arrow(draw, (255, 0, 0, 255), (x, y), (tx, ty), width=5)


def highlight(img, index, x, y, name, hper, owner, event, task_planets, health=0):
    coordinate = get_im_coordinates(x, y)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = ImageFont.truetype("./assets/Michroma-Regular.ttf", 8)
    font2 = ImageFont.truetype("./assets/Michroma-Regular.ttf", 8)
    bbox = draw.textbbox((0, 0), name, font=font, align="center", spacing=0)

    out = 2
    colors = {
        "automaton": (254 - 50, 109 - 50, 114 - 50, 200),  # Red
        "terminids": (255 - 50, 193 - 50, 0, 200),  # Yellow
        "humans": (0, 150, 150, 200),  # Cyan-like color
        "illuminate": (150, 0, 150, 200),
    }
    outline = colors[owner]

    if index in task_planets or event:
        # print(task_planets)
        outline = (255, 255, 255)
        if event:
            outline = (64, 64, 255)
    bbox2 = draw.textbbox(
        (0, 0), f"{str(hper)}\n{100-int(health)}", font=font2, align="center", spacing=0
    )
    background_box = [
        coordinate[0] - bbox[2] / 2 - 2,
        coordinate[1] - bbox[3] - 2 - 10,
        coordinate[0] + bbox[2] / 2 + 2,
        coordinate[1] - 10,
    ]

    draw.rectangle(background_box, fill=colors[owner], outline=outline, width=out)
    draw.rectangle(
        (
            [
                coordinate[0] - bbox2[2] / 2,
                background_box[3] + 20,
                coordinate[0] + bbox2[2] / 2,
                background_box[3] + 20 + bbox2[3] + 2,
            ]
        ),
        fill=colors[owner],
        outline=outline,
    )

    draw.text(
        (coordinate[0] - bbox[2] / 2, coordinate[1] - bbox[3] - 12),
        name,
        fill=(255, 255, 255),
        font=font,
        align="center",
        spacing=0,
    )
    draw.text(
        (coordinate[0] - bbox2[2] / 2, background_box[3] + 20),
        f"{str(hper)}\n{100-int(health)}",
        fill=(255, 255, 255),
        font=font2,
        align="center",
        spacing=0,
    )
    img = Image.alpha_composite(img, overlay)
    return img


def place_planet(index, frames_dict):

    filepath = f"./assets/planets/planet_{index}_rotate.gif"
    if os.path.exists(filepath):
        frames_dict[index] = []
        with Image.open(filepath) as planetimg:
            for frame in ImageSequence.Iterator(planetimg):
                frames_dict[index].append(frame.copy().convert("RGBA"))
    else:
        filepath = "./assets/planet.png"
        if os.path.exists(filepath):
            with Image.open(filepath).convert("RGBA") as planetimg:
                frames_dict[index] = [
                    planetimg.copy() for _ in range(30)
                ]  # Assuming 30 frames for PNG


def crop_image(image, coordinate, off_by, cell_size=250):
    ccr = coordinate
    bc = ccr + off_by + np.array((0, 0))
    uc = ccr - off_by
    left = max(uc[0] * cell_size, 0)
    top = max(uc[1] * cell_size, 0)
    right = min(bc[0] * cell_size, image.width)
    bottom = min(bc[1] * cell_size, image.height)
    cropped_img = image.crop((left, top, right, bottom))
    return cropped_img


def create_gif(filepath, apistat: ApiStatus):
    # create gif only if needed
    img = draw_grid(filepath)
    img = draw_supply_lines(img, apistat=apistat)
    task_planets = []
    if apistat:
        for a in apistat.assignments.values():
            assignment = a.get_first()
            task_planets.extend(assignment.get_task_planets())
    planets = {}
    lastplanets = {"version": 3, "planets": {}}
    for _, planet in apistat.planets.items():
        gpos = planet.position
        x = gpos.x
        y = gpos.y
        hper = str(planet.health_percent())
        hp = (math.ceil(planet.health_percent()) // 10) * 10
        name = str(planet.index)+":"+str(planet.name).replace(" ", "\n")
        if apistat and apistat.warall:
            for pf in apistat.warall.war_info.planetInfos:
                if pf.index == planet.index:
                    name = str(planet.index)+":"+str(planet.name).replace(" ", "\n")
                    hper = str(planet.sector)
                    break
        event = True if planet.event is not None else False
        owner = planet.currentOwner.lower()
        lastplanets["planets"][planet.index] = {
            "index": planet.index,
            "event": event,
            "x": x,
            "y": y,
            "hper": hper,
            "health": str(hp),
            "task_planets": task_planets,
            "name": name,
            "owner": owner,
        }
    if not update_lastval_file(lastplanets):
        print("No significant change.")
        return "./saveData/map.gif"

    for index, value in lastplanets["planets"].items():
        img = highlight(img, **value)
        place_planet(index, planets)

    frames = []
    for _, planet_obj in apistat.planets.items():
        gpos = planet_obj.position
        c = get_im_coordinates(gpos.x, gpos.y)
        img.alpha_composite(planets[planet_obj.index][0], (c[0] - 10, c[1] - 10))

    for frame in range(1, 30):  # Assuming 30 frames
        #        print(frame)
        frame_img = Image.new("RGBA", (img.width, img.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame_img)
        for _, planet_obj in apistat.planets.items():
            gpos = planet_obj.position
            c = get_im_coordinates(gpos.x, gpos.y)
            frame_img.alpha_composite(
                planets[planet_obj.index][frame], (c[0] - 10, c[1] - 10)
            )

        frames.append(frame_img)
    print("saving")
    # Save the frames to the buffer
    img.save(
        "./saveData/map.gif",
        format="GIF",
        save_all=True,
        default_image=True,
        interlace=False,
        append_images=frames[0:],
        duration=100,
        optimize=True,
        dispose=2,
        transparency=0,
        loop=0,
    )

    return "./saveData/map.gif"


def crop_gif(frames, coordinate, off_by, cell_size=200, one_only=False):
    # Load the GIF from the buffer

    cropped_frames = []
    for frame in frames:
        cropped_frame = crop_image(frame, coordinate, off_by, cell_size)
        cropped_frames.append(cropped_frame)
        if one_only:
            return cropped_frames
    return cropped_frames


class MapViewer(BaseView):
    """
    scrollable map.
    """

    def __init__(
        self, *, user, timeout=30 * 15, img=None, initial_coor=None, oneonly=False
    ):
        super().__init__(user=user, timeout=timeout)
        self.value = False
        self.crops = {}
        self.oneframe = not oneonly
        self.done = NotImplemented
        with Image.open(img) as planetimg:
            frames_list = []
            for frame in ImageSequence.Iterator(planetimg):
                frames_list.append(frame.copy())
            self.img = frames_list
        # self.img = [frame for frame in ImageSequence.Iterator(Image.open(img))]
        self.focus_cell = np.array(initial_coor) // CELL_SIZE

    def make_embed(self):
        self.focus_cell = np.clip(self.focus_cell, (2, 2), (10, 10))
        coors = f"Viewing cell {self.focus_cell[0]}, {self.focus_cell[1]}"
        embed = discord.Embed(
            description=f"Current galactic map view.  \n{coors}"[:4000],
            timestamp=discord.utils.utcnow(),
        )

        cropped_frames = crop_gif(
            self.img,
            self.focus_cell,
            off_by=np.array((2, 2)),
            cell_size=CELL_SIZE,
            one_only=self.oneframe,
        )
        with io.BytesIO() as image_binary:
            cropped_frames[0].save(
                image_binary,
                format="GIF",
                save_all=True,
                append_images=cropped_frames[1:],
                duration=100,
                dispose=2,
                transparency=0,
                loop=0,
            )
            image_binary.seek(0)
            file = discord.File(fp=image_binary, filename="highlighted_palmap.gif")

        embed.set_image(url="attachment://highlighted_palmap.gif")

        return embed, file

    async def on_timeout(self) -> None:
        self.value = "timeout"
        self.stop()

    @discord.ui.button(label="Up", style=discord.ButtonStyle.green, row=2)
    async def move_up(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.focus_cell += np.array((0, -1))
        # await interaction.response.defer()
        embed, file = self.make_embed()
        await interaction.response.edit_message(
            content="", embed=embed, attachments=[file]
        )

    @discord.ui.button(label="Down", style=discord.ButtonStyle.green, row=4)
    async def move_down(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.focus_cell += np.array((0, 1))
        # await interaction.response.defer()
        embed, file = self.make_embed()
        await interaction.response.edit_message(
            content="", embed=embed, attachments=[file]
        )

    @discord.ui.button(label="Left", style=discord.ButtonStyle.green, row=3)
    async def move_left(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.focus_cell += np.array((-1, 0))
        # await interaction.response.defer()
        embed, file = self.make_embed()

        await interaction.response.edit_message(
            content="", embed=embed, attachments=[file]
        )

    @discord.ui.button(label="Right", style=discord.ButtonStyle.green, row=3)
    async def move_right(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.focus_cell += np.array((1, 0))
        # await interaction.response.defer()
        embed, file = self.make_embed()

        await interaction.response.edit_message(
            content="", embed=embed, attachments=[file]
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.edit_message(content="Terminating.")
        self.stop()
