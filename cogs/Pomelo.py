import asyncio
import discord
from discord.ext import commands, tasks
import re

from discord import app_commands
import gui
from sqlitedict import SqliteDict

from dateutil.relativedelta import relativedelta
from datetime import datetime, timezone
import utility
from bot import TCBot, TCGuildTask, Guild_Task_Functions, StatusEditMessage, TC_Cog_Mixin
def get_last_day_of_month(year, month):
    next_month = datetime(year, month, 1,tzinfo=timezone.utc) + relativedelta(months=1)
    last_day = next_month - relativedelta(days=1)
    return last_day

def get_month_and_year_from_string(date_string):
    date = datetime.strptime(date_string, "%B %Y")
    month = date.month
    year = date.year
    return month, year
def get_last_day_of_string_date(date_string):
    month, year = get_month_and_year_from_string(date_string)
    last_day = get_last_day_of_month(year, month)
    return last_day

def is_user_nitro(user:discord.User):
    c1=user.accent_color != None
    c2=False
    if user.avatar:
        c2=user.avatar.is_animated()
    c3=user.banner != None
    gui.print(c1,c2,c3)
    return c1 or c2 or c3


def is_member_nitro(member:discord.Member):
    c1=member.guild_avatar != None

    c2=member.premium_since != None
    c3=is_user_nitro(member)
    gui.print(c1,c2,c3)
    return c1 or c2 or c3

async def is_cyclic(dictionary, start_key):
    visited = set()  # To keep track of visited keys
    stack = [(start_key, dictionary[start_key])]  # Start with the initial key-value pair
    taglist=dictionary['taglist']
    while stack:
        key, vt = stack.pop()
        value=vt['text']
        

        while True:
            await asyncio.sleep(0.01)
            if key in visited:
                return True  # Cycle detected

            # Find all instances of key in value
            matches = re.findall(r'\[([^\[\]]+)\]', value)
            keys_to_replace = [match for match in matches if match in taglist]
            if not keys_to_replace:
                break  # No more instances of key found

            # Replace key with its corresponding value in value
            value = value.replace(f"[{key}]", dictionary.get(key, {'text':''})['text'], 1)

            # Check if there are any new keys introduced in the updated value
            new_keys = [k for k in taglist if f'[{k}]' in value and k!='taglist']
            stack.extend((k, dictionary[k]) for k in new_keys)
        visited.add(key)
    return False  # No cycle detected

async def is_cyclic_mod(dictionary, start_key, value):
    visited = set()  # To keep track of visited keys
    stack = [(start_key, value)]  # Start with the initial key-value pair
    taglist=dictionary['taglist']
    while stack:
        key, vt = stack.pop()
        value=vt['text']
        

        while True:
            await asyncio.sleep(0.01)
            gui.gprint(key)
            if key in visited:
                gui.gprint(key,visited)
                return True  # Cycle detected

            # Check if there are any new keys introduced in the value
            new_keys = [k for k in taglist if f'[{k}]' in value and k != 'taglist']
            stack.extend((k, dictionary[k]) for k in new_keys)

            if not new_keys:
                break  # No more new keys found in the value
        visited.add(key)

    return False  # No cycle detected

async def dynamic_tag_get(dictionary,text, maxsize=2000):
    value = text
    for deep in range(32):
        matches = re.findall(r'\[([^\[\]]+)\]', value)
        keys_to_replace = [match for match in matches if match in dictionary['taglist']]

        if not keys_to_replace:
            return value
        if len(keys_to_replace)<=0:
            return value
        for key_to_replace in keys_to_replace:
            new=dictionary[key_to_replace]['text']
            if len(new)+len(value)<maxsize:
                value = value.replace('[' + key_to_replace + ']', )
                await asyncio.sleep(0.01)
    return value



class Pomelo(commands.Cog, TC_Cog_Mixin):
    """Pomelo!"""
    def __init__(self, bot):
        self.helptext=""
        self.bot=bot
        self.db = SqliteDict("./saveData/tags.sqlite")

    def cog_unload(self):
        self.db.close()
    tags = app_commands.Group(name="tags", description="Tag commands")
    @tags.command(name='create', description='create a tag')
    @app_commands.describe(tagname='tagname to add')
    @app_commands.describe(text='text of the tag.')
    async def create(self,interaction:discord.Interaction,tagname:str,text:str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        taglist=self.db.setdefault('taglist',[])
        if tagname in taglist:
            await ctx.send("Tag is already in list.")
            return
        tag={tagname:{
            'tagname':tagname,
            'user':interaction.user.id,
            'text':text,
            'lastupdate':discord.utils.utcnow()
            }
            }
        cycle_check=await is_cyclic_mod(self.db,tagname,tag[tagname])
        if cycle_check:
            await ctx.send("This value will cause a recursive loop!")
            return
        self.db['taglist'].append(tagname)
        self.db.update(tag)
        self.db.commit()
        await ctx.send(text)
    @tags.command(name='delete', description='delete a tag')
    @app_commands.describe(tagname='tagname to delete')
    async def delete(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        taglist = self.db.setdefault('taglist', [])
        if tagname not in taglist:
            await ctx.send("Tag not found.")
            return
        tag = self.db.get(tagname, {})
        if tag.get('user') == interaction.user.id:
            self.db.pop(tagname)
            taglist.remove(tagname)
            self.db.commit()
            await ctx.send(f"Tag '{tagname}' deleted.")
        else:
            await ctx.send("You don't have permission to delete this tag.")

    @tags.command(name='edit', description='edit a tag')
    @app_commands.describe(tagname='tagname to edit')
    @app_commands.describe(newtext='new text of the tag')
    async def edit(self, interaction: discord.Interaction, tagname: str, newtext: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        tag = self.db.get(tagname, {})
        
        if tag:
            if tag.get('user') == interaction.user.id:
                cycle_check=await is_cyclic_mod(self.db,tagname,{'text':newtext})
                if cycle_check:
                    await ctx.send("This value will cause a recursive loop!")
                    return
                tag['text'] = newtext
                tag['lastupdate']=discord.utils.utcnow()
                self.db[tagname] = tag
                self.db.commit()
                await ctx.send(f"Tag '{tagname}' edited.")
            else:
                await ctx.send("You don't have permission to edit this tag.")
        else:
            await ctx.send("Tag not found.")

    @tags.command(name='list', description='list all tags')
    async def listtags(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        taglist = self.db.get('taglist', [])
        if taglist:
            tags = '\n'.join(taglist)
            pageme=commands.Paginator(prefix="",suffix="",max_size=2000)
            for i in taglist:
                pageme.add_line(i)
            embeds=[]
            for e,page in enumerate(pageme.pages):
                embed=discord.Embed(title=f"Tags: {e+1}", description=page, color=discord.Color(0x00787f))
                embeds.append(embed)
            await utility.pages_of_embeds(ctx,embeds)
            await ctx.send(f"Tags:\n{tags}")
        else:
            await ctx.send("No tags found.")

    @tags.command(name='get', description='get a tag')
    @app_commands.describe(tagname='tagname to get')
    async def get(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        tag = self.db.get(tagname, {})
        if tag:
            #if is_cyclic(self.db,tagname):
            #    await ctx.send(f"WARNING!  Tag {tagname} is cyclic!")
            #    return
            text = tag.get('text')
            output=await dynamic_tag_get(self.db,text)
            to_send=f"Tag '{tagname}':\n {output}"
            if len(to_send)>2000:
                to_send=to_send[:1950]+"tag size limit."
            await ctx.send(to_send)
        else:
            await ctx.send("Tag not found.")

        
    @app_commands.command(name='guild_pomelo',description="check pomelo status of entire guild.",extras={'global':True})
    @app_commands.guild_only()
    async def allpomelo(self,interaction:discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        user=interaction.user
        nitro_pom=self.db.get('nitropom')['text']
        user_pom=self.db.get('userpom')['text']
        nitro_deadline=get_last_day_of_string_date(nitro_pom)
        user_deadline=get_last_day_of_string_date(user_pom)
        output=await dynamic_tag_get(self.db,"[pomeloinfo]\n[pomwave]")
        
        havepom=upom=nipom=nopom=0
        for user in ctx.guild.members:
            if user.discriminator=="0":
                havepom+=1
            else:
                if user.created_at<=user_deadline:
                    upom+=1
                if is_member_nitro(user):
                    if user.created_at<=nitro_deadline:
                        nipom+=1
                nopom+=1
        embed=discord.Embed(title=f"Server Pomelo Status", description='', color=discord.Color(0x00787f))
        embed.add_field(name="Already have Pomelo",value=havepom)
        embed.add_field(name="Could have pomelo",value=upom)
        embed.add_field(name="Could have pomelo because Nitro",value=nipom)
        embed.add_field(name="Can't get Pomelo Yet", value=nopom)
        await ctx.send(output,embed=embed)
        
        
        

    @app_commands.command(name='username_pomelo',description="Check if you are eligable for the new discord username.",extras={'global':True})
    @app_commands.guild_only()
    async def amipomelo(self,interaction:discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        user=interaction.user
        nitro_pom=self.db.get('nitropom')['text']
        user_pom=self.db.get('userpom')['text']
        nitro_deadline=get_last_day_of_string_date(nitro_pom)
        user_deadline=get_last_day_of_string_date(user_pom)
        await ctx.send(f"Using my sources, I'll check if you can claim a new username, or as it's called internally, a **Pomelo username**."+\
                       "I can't get a pomelo because I'm a bot, and bots are cool.\n"+\
                       "If your account was created after either of the dates below, you should be able to claim your username.\n"+\
                       "If you don't get a notification though, either **close out and restart the desktop app**, or **refresh the web browser.**\n" +\
                       "If it doesn't show up, however, please let me know via the `/nopomelo` command, because discord isn't being clear about eligability.\n"+\
                       "Nitro will only matter if you've subscribed to Nitro before March 1st."+\
                       f"\n **Nitro users:**{nitro_pom}\n **Normal users:**{user_pom}")
        if user.discriminator=="0":
            await ctx.send("It looks like you claimed a pomelo already, nice work!")
            return
        if user.created_at<=user_deadline:
            await ctx.send("You should be able to claim a pomelo username!")
        elif is_member_nitro(ctx.author):
            if user.created_at<=nitro_deadline:
                await ctx.send("I think you might be a nitro user \n You should be able to claim a pomelo username!")
            else:
                await ctx.send("You can not claim a pomelo username yet, even though you are nitro.")
        else:
            await ctx.send("I don't think you can't claim a pomelo username yet.")
     
        
    @app_commands.command(name='nopomelo',description="use this if I got it wrong and you can't pomelo yourself.",extras={'global':True})
    @app_commands.guild_only()
    async def nopomelo(self,interaction:discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        user=interaction.user
        nitro_pom=self.db.get('nitropom')['text']
        user_pom=self.db.get('userpom')['text']
        log=self.db.get('pomlog')['text']
        channel=self.bot.get_channel(int(log))
        nitro_deadline=get_last_day_of_string_date(nitro_pom)
        user_deadline=get_last_day_of_string_date(user_pom)

        user_check=user.created_at<=user_deadline
        isnitro=is_member_nitro(ctx.author)
        nitro_check=user.created_at<=nitro_deadline
        
        if user.discriminator==0:

            
            if not user_check:
                await ctx.send("So you can pomelo despite having a newer account, thank you.")
                await channel.send(f"Pomelo confirm: {user.created_at}, {nitro_pom}")
                return
            if isnitro and not nitro_check:
                await ctx.send("Looks like the nitro worked too well.")
                await channel.send(f"Nitro Pomelo confirm: {user.created_at}, {nitro_pom}")
                return
            await ctx.send("Hey, my prediction was right for you!")
        else:
            if isnitro and nitro_check:
                await ctx.send("Yeah, I've seen reports that nitro users where unable to claim usernames, thanks for letting me know.")
                await channel.send(f"Nitro Pomelo Has issue for user: {user.created_at}, {nitro_pom}")
                return
            if user_check:
                await ctx.send("If you actually do have nitro, I'm sorry.  ")
                await channel.send(f"Normal user cannot get pomelo: {user.created_at}, {nitro_pom}")
                return
            await ctx.send("It doesn't look like I was wrong though.")
            


     
        
        

        
        





        
    
    



async def setup(bot):
    await bot.add_cog(Pomelo(bot))
