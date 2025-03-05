from PIL import Image, ImageDraw, ImageFont

import math


from typing import Union
import markdown


def wrap_text(draw: ImageDraw, text: str, font: ImageFont, max_width: int) -> list[str]:
    """
    Split lines into a list of strings, delimited by max_width.
    """
    lines = []
    words = text.split()
    while words:
        line = ""
        while words and draw.textsize(line + words[0], font=font)[0] <= max_width:
            line += words.pop(0) + " "
        lines.append(line)
    return lines


FONT_STYLES = {
    "strong": {"font": ImageFont.load_default(), "modifier": "bold"},
    "em": {"font": ImageFont.load_default(), "modifier": "italic"},
    "p": {"font": ImageFont.load_default(), "modifier": "italic"},
}


def parse_markdown(markdown_text):
    # Initialize markdown parser
    md = markdown.Markdown(extensions=["extra"], output_format="html")

    # Parse Markdown text into HTML
    html_text = md.convert(markdown_text)
    html_text = html_text.replace("\n", "<p></p>")

    return html_text


class HTMLRenderer:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height
        self.image = Image.new("RGB", (width, height), (255, 255, 255))
        self.draw = ImageDraw.Draw(self.image)
        self.font = ImageFont.load_default()
        self.offset = (0, 0)
        self.position = (10, 10)  # Starting position for rendering

    def render_html_to_image(self, html_text, output_image_path):
        from lxml import etree

        html_tree = etree.fromstring(html_text, parser=etree.HTMLParser())
        self.render_node(html_tree)

        self.image.save(output_image_path)
        return self.image

    def render_node(self, node):
        print(node.tag, node)
        if node.tag == "html" or node.tag == "body":
            pass
        elif node.tag == "h1":
            self.draw.text(self.position, node.text, fill="black", font=self.font)
            self.position = (
                self.position[0],
                self.position[1] + 30,
            )  # Move down for next element
        elif node.tag == "p":
            # if node.text:      self.draw.text(self.position, node.text, fill='black', font=self.font)
            self.position = (
                self.position[0],
                self.position[1] + 20,
            )  # Move down for next element
            self.offset = (0, 0)
        elif node.tag == "strong":
            self.bold = True

        if node.text:
            bbox = self.draw.textbbox(
                (0, 0), node.text, font=self.font
            )  # Get bounding box of text
            self.draw.text(
                (self.position[0] + self.offset[0], self.position[1]),
                node.text,
                fill="black",
                font=self.font,
            )
            self.offset = (
                self.offset[0] + bbox[2] - bbox[0] + 10,
                0,
            )  # Move right for next element

        for child in node.iterchildren():
            self.render_node(child)
        if node.tag == "strong":
            self.bold = False


def markdown_to_image(markdown_text, output_image_path, width=800, height=600):
    # Create a blank image
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Load default font
    font = ImageFont.load_default()

    # Parse Markdown into HTML tree
    html_text = parse_markdown(markdown_text)

    # Render HTML tree onto image
    output_image_path = "output_image.png"
    renderer = HTMLRenderer()
    image = renderer.render_html_to_image(html_text, output_image_path)

    # Save the image
    image.save(output_image_path)
    return image


text = """
***HELLO WORLD***
*How are you?*

### Fine thank you.
"""


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    color: Union[str, tuple[int, int, int]],
    a: tuple[int, int],
    b: tuple[int, int],
    dash_length=5,
    width=1,
    offset=0,
):
    """
    Draw a dashed line from point 'a' to point 'b' with given dash length and width.

    Parameters:
    - draw: ImageDraw instance used to draw on the image.
    - color: Color of the dashed line, can be a string or tuple of RGB values.
    - a: Starting point (x, y) tuple of the line.
    - b: Ending point (x, y) tuple of the line.
    - dash_length: Length of each dash in pixels (default is 5).
    - width: Width of the line dashes (default is 1).
    - offset: Number of steps to offset the start of the dashes (default is 0).
    """

    total_length = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
    # Euclidean distance
    steps = (
        int(total_length / dash_length) // 2 * 2
    )  # Ensure we have an even number of steps
    for i in range(0, steps, 3):
        start = (a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
        end = (
            a[0] + (b[0] - a[0]) * (i + 2) / steps,
            a[1] + (b[1] - a[1]) * (i + 2) / steps,
        )
        draw.line([start, end], fill=color, width=width)


def draw_dot(
    draw: ImageDraw.ImageDraw,
    color: Union[str, tuple[int, int, int]],
    a: tuple[int, int],
    b: tuple[int, int],
    width: int = 5,
    offset=0,
):
    """
    Draw a dot somewhere between point 'a' and point 'b' with the position determined by offset.

    Parameters:
    - draw: ImageDraw instance used to draw on the image.
    - color: Color of the dot, can be a string or tuple of RGB values.
    - a: Starting point (x, y) tuple.
    - b: Ending point (x, y) tuple.
    - offset: A float between 0 and 1 representing the relative position between 'a' and 'b'.
    """

    x = a[0] + offset * (b[0] - a[0])
    y = a[1] + offset * (b[1] - a[1])
    position = (x, y)

    # draw.point(position, fill=color)

    draw.ellipse(
        [
            position[0] - width,
            position[1] - width,
            position[0] + width,
            position[1] + width,
        ],
        outline=color,
        fill=color,
    )


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    color: Union[str, tuple[int, int, int]],
    st: tuple[int, int],
    ed: tuple[int, int],
    arrowhead_length=20,
    arrowhead_angle=30,
    width=1,
    offset_a=0.2,
    offset_b=0.7,
):
    """
    Draw a colored arrow from point 'a' to point 'b' with an arrowhead pointing at 'b'.

    Parameters:
    - draw: ImageDraw instance used to draw on the image.
    - color: Color of the arrow, can be a string or tuple of RGB values.
    - a: Starting point (x, y) tuple of the arrow.
    - b: Ending point (x, y) tuple of the arrow.
    - arrowhead_length: Length of each side of the arrowhead in pixels (default is 10).
    - arrowhead_angle: Angle between the arrow shaft and each side of the arrowhead in degrees (default is 30).
    - width: Width of the arrow shaft (default is 1).
    """

    # Draw the arrow shaft

    a = (st[0] + offset_a * (ed[0] - st[0]), st[1] + offset_a * (ed[1] - st[1]))
    b = (st[0] + offset_b * (ed[0] - st[0]), st[1] + offset_b * (ed[1] - st[1]))
    draw.line([a, b], fill=color, width=width)

    # Calculate the direction of the arrow shaft
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = (dx**2 + dy**2) ** 0.5
    if length <= 0:
        length = 0.1
    direction = (dx / length, dy / length)

    # Calculate the points to draw two lines out of the target
    arrowhead_angle_rad = math.radians(arrowhead_angle)
    sin_angle = math.sin(arrowhead_angle_rad)
    cos_angle = math.cos(arrowhead_angle_rad)

    left_x = b[0] - arrowhead_length * (
        cos_angle * direction[0] - sin_angle * direction[1]
    )
    left_y = b[1] - arrowhead_length * (
        cos_angle * direction[1] + sin_angle * direction[0]
    )
    left = (left_x, left_y)

    right_x = b[0] - arrowhead_length * (
        cos_angle * direction[0] + sin_angle * direction[1]
    )
    right_y = b[1] - arrowhead_length * (
        cos_angle * direction[1] - sin_angle * direction[0]
    )
    right = (right_x, right_y)

    # Draw the arrowhead
    draw.line([b, left], fill=color, width=width)
    draw.line([b, right], fill=color, width=width)
    draw.polygon([b, left, right], fill=color)
