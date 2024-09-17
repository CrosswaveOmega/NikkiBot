"""Code for generating gifs of each planet."""

import math
import os
import random
import glob
import matplotlib.pyplot as plt
import numpy as np
import math
from matplotlib.colors import LinearSegmentedColormap
from perlin_noise import PerlinNoise
from PIL import Image, ImageDraw, ImageFont
from sklearn.cluster import KMeans

CLOUD_ALPHA = 180


BIOME_IMAGE_PATH =r"./assets/allimages/*"
OUTPUT_PATH="./assets/planets/"
FONT_PATH="./assets/Michroma-Regular.ttf"

def draw_streak(draw, xpix, ypix, lightest_color):
    start_x = random.randint(0, xpix - 1)
    start_y = random.randint(0, ypix - 1)
    length = random.randint(5, 10)
    thickness = random.randint(1, 2)
    angle = random.uniform(0, 2 * math.pi)

    end_x = start_x + int(length * math.cos(angle))
    end_y = start_y + int(length * math.sin(angle))

    end_x = min(max(end_x, 0), xpix - 1)
    end_y = min(max(end_y, 0), ypix - 1)

    draw.line(
        [(start_x, start_y), (end_x, end_y)],
        fill=(lightest_color[0], lightest_color[1], lightest_color[2], CLOUD_ALPHA),
        width=thickness,
    )


def draw_spiral(draw, xpix, ypix, lightest_color):
    cx = xpix // 2
    cy = ypix // 2
    num_turns = random.randint(2, 5)
    num_points = 100
    radius_step = 5
    angle_step = num_turns * 2 * math.pi / num_points

    points = []
    for i in range(num_points):
        angle = i * angle_step
        radius = i * radius_step
        x = cx + int(radius * math.cos(angle))
        y = cy + int(radius * math.sin(angle))
        points.append((x, y))

    draw.line(
        points,
        fill=(lightest_color[0], lightest_color[1], lightest_color[2], CLOUD_ALPHA),
        width=1,
    )


def draw_squacked_ellipse(draw, xpix, ypix, lightest_color):
    cx = random.randint(0, xpix - 1)
    cy = random.randint(0, ypix - 1)
    width = random.randint(2, 8)
    height = random.randint(2, 8)
    rotation = random.uniform(0, 2 * math.pi)

    rect = (
        cx - width // 2,
        cy - height // 2,
        cx + width // 2,
        cy + height // 2,
    )

    draw.ellipse(
        rect,
        fill=(lightest_color[0], lightest_color[1], lightest_color[2], CLOUD_ALPHA),
        outline=None,
    )


def luminance(color):
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]


def saturation(color):
    max_val = max(color)
    min_val = min(color)
    if max_val == min_val:
        return 0
    saturation_value = (max_val - min_val) / max_val
    return saturation_value


def sort_colors_by_saturation(colors):
    return sorted(colors, key=saturation)


def extract_colors(image_path, num_colors=7):
    # Open the image file
    img = Image.open(image_path)

    # Convert the image to RGB (this removes the alpha channel if present)
    img = img.convert("RGB")

    # Convert image data to a list of RGB values
    img_data = np.array(img)
    img_data = img_data.reshape((-1, 3))

    # Use k-means clustering to find the most common colors
    kmeans = KMeans(n_clusters=num_colors, random_state=1024)
    kmeans.fit(img_data)

    # Get the colors as a list of RGB values
    colors = kmeans.cluster_centers_.astype(int)
    # colors = sort_colors_by_saturation(colors)

    return colors


def render_planet(
    texture, xpix, ypix, sphere_center, sphere_radius, angle, light_dir, biome
):
    sphere_img = Image.new("RGBA", (21, 21), (0, 0, 0, 0))
    sphere_draw = ImageDraw.Draw(sphere_img)

    def get_texture_color(u, v):
        x = int(u * xpix - 1)
        y = int(v * ypix - 1)
        return tuple(texture[y, x])

    # Convert angle to radians
    angle_rad = math.radians(angle)

    for y in range(21):
        for x in range(21):
            dx = x - sphere_center[0]  # Calculate the x-distance from the sphere center
            dy = y - sphere_center[1]  # Calculate the y-distance from the sphere center
            if (
                dx**2 + dy**2 <= sphere_radius**2
            ):  # Check if the point is within the circle
                # Calculate the z-distance using Pythagorean theorem to keep the point on the sphere surface
                dz = math.sqrt(sphere_radius**2 - dx**2 - dy**2)
                nx = dx / sphere_radius  # Normalize x-distance to get the normal
                ny = dy / sphere_radius  # Normalize y-distance to get the normal
                nz = dz / sphere_radius  # Normalize z-distance to get the normal

                # Apply rotation to the normal vector
                nx_rot = nx * math.cos(angle_rad) - nz * math.sin(angle_rad)
                nz_rot = nx * math.sin(angle_rad) + nz * math.cos(angle_rad)

                # Calculate texture coordinates with the rotated normal
                u = 0.5 + (
                    math.atan2(nz_rot, nx_rot) / (2 * math.pi)
                )  # Calculate texture coordinate u
                v = 0.5 - (math.asin(ny) / math.pi)  # Calculate texture coordinate v

                color = get_texture_color(u, v)  # Get the texture color at (u, v)
                normal = np.array([nx, ny, nz])  # Construct the normal vector
                if biome == "blackhole":
                    light_intensity = 0.5  # Make the light intensity constant
                    sphere_img.putpixel((x, y), color)

                else:
                    light_intensity = np.dot(
                        normal, light_dir
                    )  # Calculate the light intensity
                    light_intensity = max(
                        0.0, light_intensity
                    )  # Ensure a minimum light intensity

                    # Adjust the light intensity to simulate a larger light source
                    light_falloff = 0.5 + 0.5 * light_intensity
                    light_intensity = max(0.5, light_falloff)

                    color = tuple(
                        int(c * light_intensity) for c in color
                    )  # Adjust the color by the light intensity
                    if color != (
                        0,
                        0,
                        0,
                    ):  # If the color is not black, set the pixel in the image
                        sphere_img.putpixel(
                            (x, y), color
                        )  # Set the pixel color in the image
    if biome == "blackhole":
        sphere_draw.ellipse([(0, 0), (20, 20)], outline="purple", width=1)
    return sphere_img


def make_new_texture(colors, nme, num_craters, num_clouds, xpix, ypix, biome_name):
    lightest_color = max(colors, key=lambda c: sum(c[:-1]))
    darkest_color = min(colors, key=lambda c: sum(c[:-1]))

    print(f"{nme} Lightest color: {lightest_color}")
    print(f"{nme} Darkest color: {darkest_color}")

    cm = LinearSegmentedColormap.from_list("", np.array(colors) / 256, 256)

    img = Image.new("RGBA", (xpix, ypix), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    noise1 = PerlinNoise(octaves=3)
    noise2 = PerlinNoise(octaves=6)
    noise3 = PerlinNoise(octaves=12)
    noise4 = PerlinNoise(octaves=24)

    pic = []
    for i in range(xpix):
        row = []
        for j in range(ypix):
            noise_val = noise1([i / xpix, j / ypix])
            noise_val += 0.5 * noise2([i / xpix, j / ypix])
            noise_val += 0.25 * noise3([i / xpix, j / ypix])
            noise_val += 0.125 * noise4([i / xpix, j / ypix])

            color = cm((noise_val + 1) / 2)
            color = tuple(int(c * 255) for c in color[:3])
            img.putpixel((i, j), tuple(color))

            row.append(255)

        pic.append(row)

    for _ in range(num_craters):
        crater_center = (random.randint(0, xpix - 1), random.randint(0, ypix - 1))
        crater_radius = random.randint(1, 2)
        draw.ellipse(
            [
                (
                    crater_center[0] - crater_radius,
                    crater_center[1] - crater_radius,
                ),
                (
                    crater_center[0] + crater_radius,
                    crater_center[1] + crater_radius,
                ),
            ],
            fill=tuple(darkest_color),
            outline=tuple(darkest_color),
            width=1,
        )

    def generate_random_clouds(xpix, ypix, num_clouds, lightest_color, img: Image):
        cloudimg = Image.new("RGBA", (xpix, ypix), (0, 0, 0, 0))
        draw = ImageDraw.Draw(cloudimg)

        for _ in range(num_clouds):
            choice = random.choice([draw_streak, draw_spiral])
            choice(draw, xpix, ypix, lightest_color)

        img.alpha_composite(cloudimg)

    if biome_name == "blackhole" or biome_name == "moon":
        num_clouds = 0
    generate_random_clouds(xpix, ypix, num_clouds, lightest_color, img)
    img.save(f"{OUTPUT_PATH}planet_{nme}_texture.png")
    return img


def generate_planet_texture(
    colors,
    num_craters,
    num_clouds,
    nme="",
    biome_name="Unknown",
    make_a_new_texture=True,
):

    xpix, ypix = 40, 40
    if make_a_new_texture:
        img = make_new_texture(
            colors, nme, num_craters, num_clouds, xpix, ypix, biome_name
        )
    textureimg = Image.open(f"{OUTPUT_PATH}planet_{nme}_texture.png")
    texture = np.array(textureimg)
    sphere_center = (10, 10)
    sphere_radius = 10

    def create_gif_with_light_variation(
        texture, sphere_center, sphere_radius, frames, output_path, biome_name
    ):
        images = []
        for frame in range(frames):

            angle = (frame / frames) * 360
            # print(angle)
            light_dir = np.array([0.8, 0, 1])
            light_dir = light_dir / np.linalg.norm(light_dir)

            sphere_img = render_planet(
                texture,
                xpix,
                ypix,
                sphere_center,
                sphere_radius,
                angle,
                light_dir,
                biome_name,
            )

            images.append(sphere_img)

        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=100,
            loop=0,
            dispose=2,
        )

    texture = np.array(textureimg)
    frames = 30
    output_path = f"{OUTPUT_PATH}{nme}_rotate.gif"
    create_gif_with_light_variation(
        texture, sphere_center, sphere_radius, frames, output_path, biome_name
    )


def threshold_color(color_tuple):
    # Divide each RGB value by 32 and round up to the nearest integer
    thresholded_tuple = tuple(int(math.ceil(value / 8) * 8) for value in color_tuple)
    return thresholded_tuple


image_paths = glob.glob(BIOME_IMAGE_PATH)

all_colors = {}
has_c = []
labels = []

for image_path in image_paths:
    filename = os.path.basename(image_path)
    filename_without_extension = os.path.splitext(filename)[0]

    distinct_colors = extract_colors(image_path, num_colors=7)
    all_colors[filename_without_extension] = distinct_colors
    has_c.append(filename_without_extension)

all_colors["swamp_base"] = np.array(
    [
        [49, 93, 140],
        [89, 139, 169],
        [67, 108, 118],
        [62, 89, 50],
        [49, 102, 61],
        [115, 238, 177],
        [198, 199, 211],
    ]
)


all_colors["blackhole"] = np.array(
    [
        [24, 24, 24],
        [24, 32, 47],
        [12, 15, 28],
        [24, 24, 24],
        [24, 32, 47],
        [12, 15, 28],
        [72, 70, 136],
    ]
)

all_colors = {
    key: np.array([threshold_color(color) for color in value])
    for key, value in all_colors.items()
}


def extract_colors_image(all_colors):

    # Create a new image where each row is one of the found colors
    color_image = Image.new(
        "RGB",
        (
            10 * 100,
            len(all_colors.keys()) * 100,
        ),
    )
    draw = ImageDraw.Draw(color_image)
    keys = list(all_colors.keys())
    for j, colors in enumerate(all_colors.values()):
        for i, color in enumerate(colors):
            draw.rectangle(
                [i * 100, j * 100, (i + 1) * 100, (j + 1) * 100], fill=tuple(color)
            )
        draw.text(
            (700, j * 100),
            f"{keys[j]}",
            font=ImageFont.truetype(FONT_PATH, 16),
        )

    return color_image


im = extract_colors_image(all_colors)
im.save(f"{OUTPUT_PATH}colorpallate.png")


def get_planet(ind: int, biome_name: str):
    labels = []
    use = all_colors.get(biome_name, None)
    if biome_name in has_c:
        return generate_planet_texture(use, 0, 2, f"planet_{ind}", biome_name)
    return None

# get_planet(64, "blackhole")
