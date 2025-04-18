import discord
from discord.ext import commands


from sqlitedict import SqliteDict


class PersonalServerConfigs(commands.Cog):
    def __init__(self, bot):
        self.helptext = "This is for personal server configuration.  Work in progress."
        self.bot = bot
        self.db = SqliteDict("./saveData/privateserverconfig.sqlite")

    def cog_unload(self):
        self.db.close()

    @commands.command()
    @commands.is_owner()
    @commands.guild_only()
    async def enable_personal_config(self, ctx):
        gid = f"g{ctx.guild.id}"
        if self.db.get(gid, None) == None:
            new = {"private_channels": {}}
            self.db.setdefault(gid, {"name": ctx.guild.name, "private_channels": {}})
            self.db.commit()
            await ctx.send(str(self.db.get(gid, "none")))
            self.db.commit()
            await ctx.send("Special config set up.")

    @commands.command()
    @commands.guild_only()
    async def create_private_channel(self, ctx):
        gid = f"g{ctx.guild.id}"
        if self.db.get(gid, None) == None:
            await ctx.send("no config detected...")
            return
        uid = f"u{ctx.author.id}"
        current_entry = self.db.get(gid)
        existing_channel = current_entry["private_channels"].get(uid, None)

        if existing_channel:
            await ctx.send(
                f"You already have a private channel: {existing_channel.mention}"
            )
        else:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(
                    read_messages=False
                ),
                ctx.author: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, manage_channels=True
                ),
            }
            new_channel = await ctx.guild.create_text_channel(
                f"{ctx.author.name}s-channel", overwrites=overwrites
            )
            await ctx.send(f"Private channel created: {new_channel.mention}")
            current_entry["private_channels"].update({uid: new_channel.id})
            self.db[gid] = current_entry
            self.db.commit()


async def setup(bot):
    pc = PersonalServerConfigs(bot)
    await bot.add_cog(pc)
