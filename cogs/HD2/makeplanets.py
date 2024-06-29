import math
import os
import random
import glob
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from perlin_noise import PerlinNoise
from PIL import Image, ImageDraw, ImageFont
from sklearn.cluster import KMeans

CLOUD_ALPHA=80
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
    width = random.randint(10, 30)
    height = random.randint(5, 15)
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


def extract_colors(image_path, num_colors=7):
    # Open the image file
    img = Image.open(image_path)

    # Convert the image to RGB (this removes the alpha channel if present)
    img = img.convert('RGB')

    # Convert image data to a list of RGB values
    img_data = np.array(img)
    img_data = img_data.reshape((-1, 3))

    # Use k-means clustering to find the most common colors
    kmeans = KMeans(n_clusters=num_colors)
    kmeans.fit(img_data)

    # Get the colors as a list of RGB values
    colors = kmeans.cluster_centers_.astype(int)


    return colors

def plot_colors(colors, num_colors=7):
    num_images = len(colors.keys())
    
    fig, ax = plt.subplots(num_images, num_colors, figsize=(18, 6*num_images))

    for i, key in enumerate(colors.keys()):
        for j in range(num_colors):
            color_block = np.zeros((100, 100, 3), dtype='uint8')
            color_block[:, :] = colors[key][j]
            ax[i, j].imshow(color_block)
            ax[i, j].set_title(key)
            ax[i, j].axis('off')

    plt.tight_layout()
    plt.show()



def generate_planet_texture(colors, num_craters, num_clouds,name=''):

    lightest_color = max(colors, key=lambda c: sum(c[:-1]))
    darkest_color = min(colors, key=lambda c: sum(c[:-1]))

    print(f'{name} Lightest color: {lightest_color}')
    print(f'{name} Darkest color: {darkest_color}')

    cm = LinearSegmentedColormap.from_list('', np.array(colors) / 255, 256)

    xpix, ypix = 40, 40
    img = Image.new('RGB', (xpix, ypix), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    noise1 = PerlinNoise(octaves=3)
    noise2 = PerlinNoise(octaves=6)
    noise3 = PerlinNoise(octaves=12)
    noise4 = PerlinNoise(octaves=24)

    pic = []
    for i in range(xpix):
        row = []
        for j in range(ypix):
            noise_val = noise1([i/xpix, j/ypix])
            noise_val += 0.5 * noise2([i/xpix, j/ypix])
            noise_val += 0.25 * noise3([i/xpix, j/ypix])
            noise_val += 0.125 * noise4([i/xpix, j/ypix])

            color = cm((noise_val+1)/2)
            color = tuple(int(c * 255) for c in color[:3])
            img.putpixel((i, j), tuple(color))

        pic.append(row)


    for _ in range(num_craters):
        crater_center = (random.randint(0, xpix-1), random.randint(0, ypix-1))
        crater_radius = random.randint(1, 2)
        draw.ellipse(
            [
                (crater_center[0] - crater_radius, crater_center[1] - crater_radius),
                (crater_center[0] + crater_radius, crater_center[1] + crater_radius),
            ],
            fill=tuple(darkest_color),
            outline=tuple(darkest_color),
            width=1,
            )
    def generate_random_clouds(xpix, ypix, num_clouds, lightest_color, draw):
        img = Image.new('RGBA', (xpix, ypix), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        for _ in range(num_clouds):
            lightest_color = (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))
            choice = random.choice([draw_streak, draw_spiral, draw_squacked_ellipse])
            choice(draw, xpix, ypix, lightest_color)
    generate_random_clouds(xpix, ypix, num_clouds, lightest_color, draw)

    texture = np.array(img)

    sphere_img = Image.new('RGBA', (21, 21), (0, 0, 0,0))
    sphere_draw = ImageDraw.Draw(sphere_img)

    sphere_center = (9, 9)
    sphere_radius = 10

    light_dir = np.array([0.5, 0.5, 1.0])  # Adjust as needed and normalize below
    light_dir = light_dir / np.linalg.norm(light_dir)  # Normalize the light direction


    def get_texture_color(u, v):
        x = int(u * xpix-1)
        y = int(v * ypix-1)
        return tuple(texture[y,x])

    for y in range(21):
        for x in range(21):
            dx = x - sphere_center[0]
            dy = y - sphere_center[1]
            if dx**2 + dy**2 <= sphere_radius**2:
                dz = math.sqrt(sphere_radius**2 - dx**2 - dy**2)
                nx = dx / sphere_radius
                ny = dy / sphere_radius
                nz = dz / sphere_radius
                u = 0.5 + (math.atan2(nz, nx) / (2 * math.pi))
                v = 0.5 - (math.asin(ny) / math.pi)
                color = get_texture_color(u, v)
                normal = np.array([nx, ny, nz])
                light_intensity = np.dot(normal, light_dir)
                light_intensity = max(0.7, light_intensity)
                color = tuple(int(c * light_intensity) for c in color)
                if color!=(0,0,0):
                    sphere_img.putpixel((x, y), color)

    sphere_img.save(f'./assets/planets/{name}.png')
    return sphere_img

image_paths = glob.glob(r"./assets/allimages/*")

all_colors = {}
has_c=[]
labels = []

for image_path in image_paths:
    filename= os.path.basename(image_path)
    filename_without_extension = os.path.splitext(filename)[0]
    
    distinct_colors = extract_colors(image_path, num_colors=7)
    all_colors[filename_without_extension]=distinct_colors
    has_c.append(filename_without_extension)

# all_colors['highlands'] = np.array([
#         [128, 128, 105],
#         [186, 186, 150],
#         [105, 105, 89],
#         [139, 139, 122],
#         [160, 160, 130],
#         [205, 205, 180],
#         [245, 245, 220]
#     ])
print(all_colors)

def extract_colors_image(all_colors):
    


    # Create a new image where each row is one of the found colors
    color_image = Image.new('RGB', (10 * 100,len(all_colors.keys())*100,))
    draw = ImageDraw.Draw(color_image)
    keys=list(all_colors.keys())
    for j, colors in enumerate(all_colors.values()):
        for i, color in enumerate(colors):
            draw.rectangle(
                [i*100, j * 100, (i+1)*100, (j+1) * 100],
                fill=tuple(color)
            )
        draw.text((700, j * 100), f"{keys[j]}", font=ImageFont.truetype("arial.ttf", 30))

    return color_image


def get_planet(ind,biome_name):
    labels = []
    use=all_colors.get(biome_name,None)
    if biome_name in has_c:
        return generate_planet_texture(use,3,2,f"planet_{ind}")
    return None


