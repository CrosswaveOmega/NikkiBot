import io
import math
import os
import json
import discord
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from .GameStatus import ApiStatus
from utility.views import BaseView
from utility.image_functions import draw_arrow

SCALE = 1.0
CELL_SIZE = 200
GRIDDRAW = False


def crop_png(image, focus_cell, cell_size=CELL_SIZE, one_only=False):
    """
    Crop the image based on the current focus cell and the given cell size.
    Returns a single PNG image for the current view.
    """
    x_start = focus_cell[0] * cell_size
    y_start = focus_cell[1] * cell_size
    x_end = x_start + cell_size
    y_end = y_start + cell_size

    cropped_image = image.crop((x_start, y_start, x_end, y_end))

    if one_only:
        return cropped_image

    return cropped_image  # Return the cropped image; no need for multi-frame logic


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
    coordinate = (
        int(round(x * 1000.0 * SCALE + 1000 * SCALE, 0)),
        int(round(1000 * SCALE - y * 1000.0 * SCALE, 1)),
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

    font = ImageFont.truetype("./assets/ChakraPetch-SemiBold.ttf", 12)
    font2 = ImageFont.truetype("./assets/ChakraPetch-SemiBold.ttf", 12)
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
        outline = (255, 255, 255)
        if event:
            outline = (64, 64, 255)
    bbox2 = draw.textbbox((0, 0), f"{str(hper)}", font=font2, align="center", spacing=0)
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
        f"{str(hper)}",
        fill=(255, 255, 255),
        font=font2,
        align="center",
        spacing=0,
    )
    img = Image.alpha_composite(img, overlay)
    return img


def place_planet(index, frames_dict):
    filepath = f"./assets/planets/planet_{index}.png"
    if os.path.exists(filepath):
        frames_dict[index] = []
        with Image.open(filepath) as planetimg:
            frames_dict[index] = [planetimg.convert("RGBA")]
    else:
        filepath = "./assets/planet.png"
        if os.path.exists(filepath):
            with Image.open(filepath).convert("RGBA") as planetimg:
                frames_dict[index] = [
                    planetimg.convert("RGBA") for _ in range(1)
                ]  # Only one frame for PNG


def create_png(filepath, apistat: ApiStatus):
    # Create PNG image
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
        hper = str(planet.sector_id) + ":" + str(planet.sector)
        hp = (math.ceil(planet.health_percent()) // 10) * 10
        name = str(planet.index) + ":" + str(planet.name).replace(" ", "\n")
        if apistat and apistat.warall:
            for pf in apistat.warall.war_info.planetInfos:
                if pf.index == planet.index:
                    name = str(planet.name).replace(" ", "\n")
                    hper = str(pf.sector) + ":" + str(planet.sector)
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
        return "./saveData/map.png"

    for index, value in lastplanets["planets"].items():
        img = highlight(img, **value)
        place_planet(index, planets)

    for _, planet_obj in apistat.planets.items():
        gpos = planet_obj.position
        c = get_im_coordinates(gpos.x, gpos.y)
        img.alpha_composite(planets[planet_obj.index][0], (c[0] - 10, c[1] - 10))

    print("saving")
    # Save as a PNG file instead of a GIF
    img.save("./saveData/map.png", format="PNG")

    return "./saveData/map.png"


class MapViewer(BaseView):
    """
    Scrollable map that generates and interacts with a single PNG.
    """

    def __init__(
        self, *, user, timeout=30 * 15, img=None, initial_coor=None, oneonly=False
    ):
        super().__init__(user=user, timeout=timeout)
        self.value = False
        self.crops = {}
        self.oneframe = not oneonly
        self.done = NotImplemented

        # Load the PNG image
        with Image.open(img) as planetimg:
            self.img = planetimg.convert("RGBA")

        # Set the focus cell based on the initial coordinates
        self.focus_cell = np.array(initial_coor) // CELL_SIZE

    def make_embed(self):
        """
        Generate the embed for the map, focusing on the current cell.
        """
        self.focus_cell = np.clip(self.focus_cell, (2, 2), (10, 10))
        coors = f"Viewing cell {self.focus_cell[0]}, {self.focus_cell[1]}"
        embed = discord.Embed(
            description=f"Current galactic map view.  \n{coors}"[:4000],
            timestamp=discord.utils.utcnow(),
        )

        # Crop the image based on the focus_cell
        cropped_frame = crop_png(
            self.img,
            self.focus_cell,
            cell_size=CELL_SIZE,
            one_only=self.oneframe,
        )

        # Save the cropped image as a PNG
        with io.BytesIO() as image_binary:
            cropped_frame.save(image_binary, format="PNG")
            image_binary.seek(0)
            file = discord.File(fp=image_binary, filename="highlighted_palmap.png")

        embed.set_image(url="attachment://highlighted_palmap.png")

        return embed, file

    async def on_timeout(self) -> None:
        """
        Handle the timeout event.
        """
        self.value = "timeout"
        self.stop()

    @discord.ui.button(label="Up", style=discord.ButtonStyle.green, row=2)
    async def move_up(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """
        Move the view up by one cell.
        """
        self.focus_cell += np.array((0, -1))
        embed, file = self.make_embed()
        await interaction.response.edit_message(
            content="", embed=embed, attachments=[file]
        )

    @discord.ui.button(label="Down", style=discord.ButtonStyle.green, row=4)
    async def move_down(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """
        Move the view down by one cell.
        """
        self.focus_cell += np.array((0, 1))
        embed, file = self.make_embed()
        await interaction.response.edit_message(
            content="", embed=embed, attachments=[file]
        )

    @discord.ui.button(label="Left", style=discord.ButtonStyle.green, row=3)
    async def move_left(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """
        Move the view left by one cell.
        """
        self.focus_cell += np.array((-1, 0))
        embed, file = self.make_embed()
        await interaction.response.edit_message(
            content="", embed=embed, attachments=[file]
        )

    @discord.ui.button(label="Right", style=discord.ButtonStyle.green, row=3)
    async def move_right(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """
        Move the view right by one cell.
        """
        self.focus_cell += np.array((1, 0))
        embed, file = self.make_embed()
        await interaction.response.edit_message(
            content="", embed=embed, attachments=[file]
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Cancel the operation and stop the view.
        """
        self.value = False
        await interaction.response.edit_message(content="Terminating.")
        self.stop()
