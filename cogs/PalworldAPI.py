import aiohttp
import gui
import discord
import asyncio

# import datetime

from bot import (
    TCBot,
    TC_Cog_Mixin,
)
from discord.ext import commands


from discord.app_commands import Choice



class ToChoice(commands.Converter):
    async def convert(self, ctx, argument):
        if not ctx.interaction:
            if type(argument) == str:
                choice = Choice(name="fallback", value=argument)
                return choice
        else:
            return argument

def capitalize_first_letter(string: str) -> str:
    return string.capitalize() if string else ''


class PalworldAPI(commands.Cog, TC_Cog_Mixin):
    """A palworld command"""

    def __init__(self, bot):
        self.bot: TCBot = bot
        #self.session=aiohttp.ClientSession() 

    def cog_unload(self):
        pass
        # Remove the task function.
        
        

    @commands.command()
    async def palget(self, ctx, pal_name: str):
        """Experimental palworld API wrapper."""
        # Convert the timestamp string to a datetime object
        async with aiohttp.ClientSession() as session:
            _data_call = await session.get(f"https://api.palshome.org/v1/data/{pal_name}", headers={"api-key": self.bot.keys.get('palapi',None)}) # Let's gather our data about the provided Pal from the endpoint.
            if _data_call.status != 200: # If the API response returns no data, let's stop the command execution here and send a message.
                return await ctx.send("I'm sorry but i couldn't find the Pal you're looking for, check for any typo or error and try again")

            # Otherwise let's continue with our data now being here.
            _data = await _data_call.json() # We convert the response into JSON.
            print(_data)
        # Now you're free to do anything you want with the Pal data!
        pal_data=_data
        stats = pal_data['extras']['stats']
        # Add fields for stats
        stats = pal_data['extras']['stats']
        catchable="Catchable." if pal_data['is_catchable'] is True else ""
        boss="Can appear as boss." if pal_data['is_boss'] is True else ""
        desc=f"{pal_data['description']}\n  `Walk:{stats['walk_speed']},Run:{stats['run_speed']},RideSprint:{stats['ride_sprint_speed']},Hunger:{pal_data['extras']['hunger']}`"
        embed = discord.Embed(
        title=f"Pal Name: {pal_data['pal_name']}",
        description=desc,
        color=discord.Color.green()  # You can change the color as per your preference
        )

        embed.set_thumbnail(url=pal_data['image'])
        elements=','.join(ele for ele in pal_data['elements'])
        embed.set_author(name=f"Paldex no {pal_data['paldex_position']}.  {elements}")
        # Add fields for basic information

       
        embed.add_field(name="Stats", value=f"`HP:` {stats['hp']}\n`MeleeAttack:` {stats['meele_attack']}\n `RangedAttack`: {stats['shot_attack']}\n`Defense:` {stats['defense']}\n`Support:` {stats['support']}", inline=True)

        works="\n".join([f"{i.capitalize()}: {work}" for i, work in pal_data['works'].items()])
        embed.add_field(name="Works", value=f"{works}", inline=True)

        # Add skills
        skills=pal_data['extras']['skills']
        active_skills = skills['active']
        skills_str = "\n".join(
            [f"Lvl.{skill['unlocks_at_level']}:**{skill['name']}** `POW:{skill['power']}`: {skill['element']} \n{skill['description']}".strip() for skill in active_skills]
            )
        embed.add_field(name="Active Skills", value=skills_str, inline=False)

        # Add partner
        if pal_data['extras']['skills']['partner']:
            partner = pal_data['extras']['skills']['partner']
            embed.add_field(name=f"Partner Skill: {partner['name']}", value=f"{partner['description']}", inline=False)
        # Add passive
        if pal_data['extras']['skills']['passive']:
            passive = pal_data['extras']['skills']['passive']
            embed.add_field(name=f"Passive Skill: {passive['name']}", value=f"{passive['description']}", inline=False)

        # Add drops
        embed.add_field(name="Drops", value=", ".join(pal_data['drops']), inline=True)

        # Add locations
        embed.add_field(name="Locations", value=f"[Day]({pal_data['locations']['day']}) - [Night]({pal_data['locations']['night']})\n{pal_data['extras']['rarity']}", inline=True)
        embed.add_field(name="Size", value=pal_data['extras']['size'], inline=True)

        
        embed.set_footer(text=f"{catchable}{boss}  Price:{stats['price_market']}")
        # Finally we send it to the channel where the command has been used!
        return await ctx.send(embed=embed)


async def setup(bot):
    gui.dprint(__name__)
    # from .ArchiveSub import setup
    # await bot.load_extension(setup.__module__)
    await bot.add_cog(PalworldAPI(bot))


async def teardown(bot):
    # from .ArchiveSub import setup
    # await bot.unload_extension(setup.__module__)
    print('closing.')
    await bot.remove_cog("PalworldAPI")
