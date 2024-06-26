import io
import discord
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from .GameStatus import ApiStatus
from .helldive import Planet

CELL_SIZE = 200
from utility.views import BaseView


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


def get_im_coordinates(x, y):
    coordinate = x * 1000.0 + 1000, 1000 - y * 1000.0
    return coordinate


def draw_supply_lines(img, color=(0, 255, 0, 200), apistat: ApiStatus = None):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for index, planet in apistat.planets.items():
        gpos = planet.position
        x, y = get_im_coordinates(gpos.x, gpos.y)
        waypoints = planet.waypoints
        for ind in waypoints:
            target = apistat.planets[ind]
            tgpos = target.position
            tx, ty = get_im_coordinates(tgpos.x, tgpos.y)
            draw.line(
                [(x, y), (tx, ty)],
                fill=color,
                width=1,
            )
        waypoints = planet.attacking
        for ind in waypoints:
            target = apistat.planets[ind]
            tgpos = target.position
            tx, ty = get_im_coordinates(tgpos.x, tgpos.y)
            draw.line(
                [(x, y), (tx, ty)],
                fill=(255, 0, 0, 200),
                width=3,
            )
    img = Image.alpha_composite(img, overlay)
    return img


def highlight(img, planet: Planet, color=(255, 0, 0, 200), apistat: ApiStatus = None):
    gpos = planet.position
    x, y = gpos.x, gpos.y
    task_planets=[]
    if apistat:
        for a in apistat.assignments.values():
            assignment=a.get_first()
            task_planets.extend(assignment.get_task_planets())
    coordinate = x * 1000.0 + 1000, 1000 - y * 1000.0
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    name = str(planet.name).replace(" ", "\n")
    font = ImageFont.truetype("./assets/Michroma-Regular.ttf", 10)
    font2 = ImageFont.truetype("./assets/Michroma-Regular.ttf", 8)
    bbox = draw.textbbox((0, 0), name, font=font, align="center")
    
    hper=str(planet.health_percent())
    bbox2 = draw.textbbox(
        (0, 0), str(hper), font=font2, align="center"
    )
    background_box = [
        coordinate[0] - bbox[2] / 2,
        coordinate[1] - bbox[3] / 2,
        coordinate[0] + bbox[2] / 2,
        coordinate[1] + bbox[3] / 2,
    ]
    owner = planet.currentOwner.lower()
    colors = {
        "automaton": (254 - 50, 109 - 50, 114 - 50, 200),  # Red
        "terminids": (255 - 50, 193 - 50, 0, 200),  # Yellow
        "humans": (0, 150, 150, 200),  # Cyan-like color
        "illuminate": (150, 0, 150, 200),
    }
    outline=colors[owner]

    out=2
    if planet.index in task_planets:
        out=5
        hper=f"!!{hper}"
        outline=(255,255,255)
    draw.rectangle(background_box, fill=colors[owner], outline=outline, width=out)
    draw.rectangle(
        (
            [
                background_box[0],
                background_box[3],
                background_box[0] + bbox2[2],
                background_box[3] + bbox2[3],
            ]
        ),
        fill=colors[owner],
        outline=outline,
    )
    draw.text(
        (coordinate[0] - bbox[2] / 2, coordinate[1] - bbox[3] / 2),
        name,
        fill=(255, 255, 255),
        font=font,
        align="center",
    )
    draw.text(
        (background_box[0], background_box[3]),
        hper,
        fill=(255, 255, 255),
        font=font2,
        align="center",
    )
    img = Image.alpha_composite(img, overlay)
    return img


def crop_image(image, coordinate, off_by, cell_size=200):
    ccr = coordinate
    bc = ccr + off_by + np.array((2, 2))
    uc = ccr - off_by
    left = max(uc[0] * cell_size, 0)
    top = max(uc[1] * cell_size, 0)
    right = min(bc[0] * cell_size, image.width)
    bottom = min(bc[1] * cell_size, image.height)
    cropped_img = image.crop((left, top, right, bottom))
    return cropped_img


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
        self.img = img
        self.focus_cell = np.array(initial_coor) // CELL_SIZE


    def make_embed(self):
        coors = f"Viewing cell {self.focus_cell[0]}, {self.focus_cell[1]}"
        embed = discord.Embed(
            description=f"Current galactic map view.  \n{coors}"[:4000],
            timestamp=discord.utils.utcnow(),
        )

        cropped_img = crop_image(self.img, self.focus_cell, off_by=np.array((1, 1)))
        with io.BytesIO() as image_binary:
            cropped_img.save(image_binary, "PNG")
            image_binary.seek(0)
            file = discord.File(fp=image_binary, filename="highlighted_palmap.png")

        embed.set_image(url="attachment://highlighted_palmap.png")

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
