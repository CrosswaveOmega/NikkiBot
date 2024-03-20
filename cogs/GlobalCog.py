import discord

# import datetime


from discord.ext import commands

from discord import app_commands
from bot import TC_Cog_Mixin, super_context_menu
import cogs.ResearchAgent as ra

async def owneronly(interaction: discord.Interaction):
    return await interaction.client.is_owner(interaction.user)

class Global(commands.Cog, TC_Cog_Mixin):
    """General commands"""

    def __init__(self, bot):
        self.helptext = "Some assorted testing commands."
        self.bot = bot
        self.globalonly=True
        
        self.init_context_menus()


    @super_context_menu(name="Extracool",flags='user')
    async def coooler(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        cont=message.content
        guild=message.guild
        embed=discord.Embed(
            description=f"It says *{message.content}"

        )
        print(cont,guild,interaction.guild.id)
        
        if hasattr(message,'author'):
            embed.add_field(name="Author",value=f"* {str(message.author)}{type(message.author)}, ")

        if hasattr(message,'jump_url'):
            embed.add_field(name="url",value=f"* {str(message.jump_url)}, ")
        await interaction.response.send_message(
            content="Message details below.",
            embed=embed,
        )

    
    @super_context_menu(name="usercool",flags='user')
    async def coooler2(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        embed=discord.Embed(
            description=f"This user is {user}"

        )

        await interaction.response.send_message(
            content="User details below.",
            embed=embed,
        )
    @app_commands.command(name="search", description="search the interwebs.")
    @app_commands.describe(query="Query to search google with.")
    @app_commands.install_types(guilds=True, users=True)
    async def websearch(self, interaction: discord.Interaction, query:str) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        mess=await ctx.send("<a:LoadingBlue:1206301904863502337> Searching")
        results = ra.tools.google_search(ctx.bot, query, 7)
        allstr = ""
        emb = discord.Embed(title=f"Search results {query}")
        readable_links = []

        def indent_string(inputString, spaces=2):
            indentation = " " * spaces
            indentedString = "\n".join(
                [indentation + line for line in inputString.split("\n")]
            )
            return indentedString

        outputthis = f"### Search results for {query} \n\n"
        for r in results["items"]:
            desc = r.get("snippet", "NA")
            allstr += r["link"] + "\n"
            emb.add_field(
                name=f"{r['title'][:200]}",
                value=f"{r['link']}\n{desc}"[:1000],
                inline=False,
            )
            outputthis += f"+ **Title: {r['title']}**\n **Link:**{r['link']}\n **Snippit:**\n{indent_string(desc,1)}"
        await mess.edit(content=None,embed=emb)

    @app_commands.command(name="supersearch", description="use db search.")
    @app_commands.describe(query="Query to search DB for")
    @app_commands.install_types(guilds=True, users=True)
    async def doc_talk(self, interaction: discord.Interaction, query:str) -> None:
        """get bot info for this server"""
        owner=await interaction.client.is_owner(interaction.user)
        if not owner:
            await interaction.response.send_message("This command is owner only.")
            return
        ctx: commands.Context = await self.bot.get_context(interaction)
        mess=await ctx.send("<a:LoadingBlue:1206301904863502337> Searching")
        try:
            ans,source,_=await ra.actions.research_op(query, 9)
            emb = discord.Embed(description=ans)
            emb.add_field(name="source", value=str(source)[:1000], inline=False)
            await mess.edit(content=None,embed=emb)
        except Exception as e:
            await ctx.send("something went wrong...")



    @app_commands.command(name="pingtest", description="ping")
    @app_commands.install_types(guilds=True, users=True)
    async def ping(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        await interaction.response.send_message("Reading you loud and clear!")

    
    
    @app_commands.command(name="context_test", description="ping")
    @app_commands.install_types(guilds=True, users=True)
    async def ping2(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        await interaction.response.send_message("Reading you loud and clear!")


    

async def setup(bot):
    await bot.add_cog(Global(bot))
