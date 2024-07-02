import os
import re
import discord
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


from datetime import datetime, timedelta, timezone

from discord.ext import commands, tasks

from discord import Webhook, ui
import site

from discord.utils import escape_markdown
import re
from typing import Union
import markdown
from PIL import Image, ImageDraw, ImageFont





def wrap_text(draw: ImageDraw, text: str, font: ImageFont, max_width: int) -> list[str]:
    '''
    Split lines into a list of strings, delimited by max_width.    
    '''
    lines = []
    words = text.split()
    while words:
        line = ''
        while words and draw.textsize(line + words[0], font=font)[0] <= max_width:
            line += (words.pop(0) + ' ')
        lines.append(line)
    return lines




FONT_STYLES = {
    'strong': {'font': ImageFont.load_default(), 'modifier': 'bold'},
    'em': {'font': ImageFont.load_default(), 'modifier': 'italic'},
    'p':{'font': ImageFont.load_default(), 'modifier': 'italic'}
}

def parse_markdown(markdown_text):
    # Initialize markdown parser
    md = markdown.Markdown(extensions=['extra'],output_format='html')

    # Parse Markdown text into HTML
    html_text = md.convert(markdown_text)
    html_text=html_text.replace('\n', '<p></p>')


    return html_text

class HTMLRenderer:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height
        self.image = Image.new("RGB", (width, height), (255, 255, 255))
        self.draw = ImageDraw.Draw(self.image)
        self.font = ImageFont.load_default()
        self.offset = (0,0)
        self.position = (10, 10)  # Starting position for rendering

    def render_html_to_image(self, html_text, output_image_path):
        from lxml import etree
        html_tree = etree.fromstring(html_text, parser=etree.HTMLParser())
        self.render_node(html_tree)

        self.image.save(output_image_path)
        return self.image

    def render_node(self, node):
        print(node.tag, node)
        if node.tag == 'html' or node.tag == 'body':
            pass
        elif node.tag == 'h1':
            self.draw.text(self.position, node.text, fill='black', font=self.font)
            self.position = (self.position[0], self.position[1] + 30)  # Move down for next element
        elif node.tag == 'p':
            #if node.text:      self.draw.text(self.position, node.text, fill='black', font=self.font)
            self.position = (self.position[0], self.position[1] + 20)  # Move down for next element
            self.offset=(0,0)
        elif node.tag == 'strong':
            self.bold=True

        if node.text:
            bbox = self.draw.textbbox((0, 0), node.text, font=self.font)  # Get bounding box of text
            self.draw.text((self.position[0]+self.offset[0], self.position[1]), node.text, fill='black', font=self.font)
            self.offset = (self.offset[0] + bbox[2] - bbox[0] + 10,0)  # Move right for next element


        for child in node.iterchildren():
            self.render_node(child)
        if node.tag == 'strong':
            self.bold=False

def markdown_to_image(markdown_text, output_image_path, width=800, height=600):
    # Create a blank image
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Load default font
    font = ImageFont.load_default()
    
    # Parse Markdown into HTML tree
    html_text = parse_markdown(markdown_text)
    
    # Render HTML tree onto image
    output_image_path = 'output_image.png'
    renderer = HTMLRenderer()
    image=renderer.render_html_to_image(html_text, output_image_path)

    # Save the image
    image.save(output_image_path)
    return image
text='''
***HELLO WORLD***
*How are you?*

### Fine thank you.
'''
