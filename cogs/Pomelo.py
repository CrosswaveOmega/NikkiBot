import asyncio
import discord
from discord.ext import commands, tasks
import re

from discord import app_commands

from sqlitedict import SqliteDict

from dateutil.relativedelta import relativedelta
from datetime import datetime, timezone
import gui
import utility
from utility import MessageTemplates
from bot import TCBot, TCGuildTask, Guild_Task_Functions, StatusEditMessage, TC_Cog_Mixin
import numpy as np


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
    return c2 or c3


def is_member_nitro(member:discord.Member):
    c1=member.guild_avatar != None

    c2=member.premium_since != None
    c3=is_user_nitro(member)
    gui.print(c1,c2,c3)
    return c1 or c2 or c3


def is_cyclic_i(dictionary, start_key):
    '''Determine if the passed in key will render a recursive reference somewhere.'''
    stack = [(start_key, set(), [start_key])]

    while stack:
        key, visited, steps = stack.pop()
        
        if key in visited:
            return True
        
        visited.add(key)
        value = dictionary[key]['text']
        matches = re.findall(r'\[([^\[\]]+)\]', value)
        keys_to_check = [match for match in matches if match in dictionary['taglist']]
        
        for next_key in keys_to_check:
            steps2=steps.copy()
            steps2.append(next_key)
            stack.append((next_key, visited.copy(),steps2))

    return False

def is_cyclic_mod(dictionary, start_key, valuestart):
    #Check if a key should be added.
    stack = [(start_key, set(),[start_key])]

    while stack:
        key, visited,steps = stack.pop()
        if key in visited:
            return True,steps
        visited.add(key)
        value=''
        if key==start_key: value=valuestart
        else: value = dictionary[key]['text']
        matches = re.findall(r'\[([^\[\]]+)\]', value)
        keys_to_check = [match for match in matches if match in dictionary['taglist']or match==start_key]
        for next_key in keys_to_check:
            steps2=steps.copy()
            steps2.append(next_key)
            stack.append((next_key, visited.copy(),steps2))
    return False,0

async def dynamic_tag_get(dictionary,text, maxsize=2000):
    value = text
    
    gui.gprint(dictionary['taglist'])
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
                value = value.replace('[' + key_to_replace + ']', new)
                await asyncio.sleep(0.01)
    value=value.replace("\\n","\n")
    return value



class Pomelo(commands.Cog):
    """Pomelo!"""
    def __init__(self, bot):
        self.helptext=""
        self.bot=bot
        self.db = SqliteDict("./saveData/tags.sqlite")
        taglist=[]
        for i, v in self.db.items():
            if i!='taglist':
                taglist.append(i)
        self.db.update({'taglist':taglist})

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
        cycle_check,steps= is_cyclic_mod(self.db,tagname,text)
        if cycle_check:
            await MessageTemplates.tag_message(
                ctx,
                f"The text will expand infinitely at keys {str(steps)}.",
                tag=tag[tagname],
                title="Tag creation error.",
                ephemeral=False
            )
            return
        taglist.append(tagname)
        self.db.update(tag)
        self.db.update({'taglist':taglist})
        self.db.commit()
        await MessageTemplates.tag_message(
            ctx,
            f"Tag {tagname} created, access it with /tags get",
            tag=tag[tagname],
            title="Tag created",
            ephemeral=False
        )
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
            tag=self.db.pop(tagname)
            taglist.remove(tagname)
            self.db.commit()
            await MessageTemplates.tag_message(
                ctx,
                f"Tag {tagname} Deleted, access it with /tags get",
                tag=tag,
                title="Tag deleted.",
                ephemeral=False
            )
        else:
            await MessageTemplates.tag_message(
                ctx,
                f"You don't have permission to delete this tag.",
                title="Tag delete error."
            )

    @tags.command(name='edit', description='edit a tag')
    @app_commands.describe(tagname='tagname to edit')
    @app_commands.describe(newtext='new text of the tag')
    async def edit(self, interaction: discord.Interaction, tagname: str, newtext: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        tag = self.db.get(tagname, {})
        
        if tag:
            if tag.get('user') == interaction.user.id:

                cycle_check,steps= is_cyclic_mod(self.db,tagname,newtext)
                if cycle_check:
                    await MessageTemplates.tag_message(
                        ctx,
                        f"The text will expand infinitely at keys {str(steps)}.",
                        tag=tag,
                        title="Tag edit error.",
                        ephemeral=False
                    )
                    return
                tag['text'] = newtext
                tag['lastupdate']=discord.utils.utcnow()
                self.db[tagname] = tag
                self.db.commit()
                await ctx.send(f"Tag '{tagname}' edited.")
            else:
                await MessageTemplates.tag_message(
                        ctx,
                        f"You don't have permission to edit this tag.",
                        title="Tag edit error."
                    )
        else:
            await MessageTemplates.tag_message(
                ctx, f"Tag not found",  title="Tag edit error."
            )

    @tags.command(name='list', description='list all tags')
    async def listtags(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        taglist = self.db.get('taglist')
        if taglist:
            # Loop through the dictionary and create an Embed object for each set of key-value pairs
            embed_list,e=[],0
            for t in taglist:
                key, value = t,self.db.get(t)['text']
                # Check if the Embed list is empty or if the last Embed object has 4 fields already
                if not embed_list or len(embed_list[-1].fields) == 4:
                    # If so, create a new Embed object
                    embed = discord.Embed(title=f"Tags: {e+1}", color=discord.Color(0x00787f))
                    # Add the first field to the new Embed object
                    if len(value)>1010:
                        value=value[:1010]
                        value+="..."

                    embed.add_field(name=key, value=value, inline=False)
                    # Add the new Embed object to the list
                    embed_list.append(embed)
                    e+=1
                else:
                    # If not, add the current key-value pair as a new field to the last Embed object
                    embed_list[-1].add_field(name=key, value=value, inline=False)

            await utility.pages_of_embeds(ctx,embed_list)

        else:
            await MessageTemplates.tag_message(
                ctx, f"No tags found"
            )

    @tags.command(name='get', description='get a tag')
    @app_commands.describe(tagname='tagname to get')
    async def get(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        tag = self.db.get(tagname, {})
        if tag:
            if is_cyclic_i(self.db,tagname):
                await ctx.send(f"WARNING!  Tag {tagname} is cyclic!")
                return
            text = tag.get('text')
            output=await dynamic_tag_get(self.db,text)
            to_send=f"{output}"
            if len(to_send)>2000:
                to_send=to_send[:1950]+"tag size limit."
            await ctx.send(to_send)
        else:
            await MessageTemplates.tag_message(
                ctx, f"Tag not found."
            )

    @tags.command(name='getraw', description="get a tag's raw text")
    @app_commands.describe(tagname='tagname to get')
    async def getraw(self, interaction: discord.Interaction, tagname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        tag = self.db.get(tagname, {})
        if tag:
            if is_cyclic_i(self.db,tagname):
                await ctx.send(f"WARNING!  Tag {tagname} is cyclic!")
                return
            text = tag.get('text')
            output=text
            await MessageTemplates.tag_message(
                ctx, f"Displaying raw tag text.",
                tag=tag,
                title='Raw Tag Text.'
            )

        else:
            await MessageTemplates.tag_message(
                ctx, f"Tag not found."
            )
        
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
        wave=self.db.get('pwave')['text']
        note=self.db.get('pomeloinfo')['text']
        nitro_deadline=get_last_day_of_string_date(nitro_pom)
        user_deadline=get_last_day_of_string_date(user_pom)
        await ctx.send(f"Using my sources, I'll check if you can claim a new username, or as it's called internally, a **Pomelo username**."+\
                       "If your account was created after either of the dates below, you should be able to claim your username.\n"+\
                       "If you don't get a notification though, either **close out and restart the desktop app**, or **refresh the web browser.**\n" +\
                       "If it doesn't show up, however, please let me know via the `/nopomelo` command, because discord isn't being clear about it's rollout.\n"+\
                       f"{note}"+\
                       f"\n **Wave: {wave}**\n**Nitro users:**{nitro_pom}\n **Normal users:**{user_pom}")
        if user.discriminator=="0":
            await ctx.send("It looks like you claimed a pomelo already, nice work!")
            return
        if user.created_at<=user_deadline:
            await ctx.send("You should be able to claim a pomelo username!")
        elif is_member_nitro(ctx.author):
            if user.created_at<=nitro_deadline:
                await ctx.send("Despite having an account made after the nitro wave, the Nitro waves are bugged.  I don't know if you can get a Pomelo as of now.")
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

    @commands.command()
    async def tagcycletest(self,ctx):
        '''Test the tag render.'''
        cases = [{
            'taglist':['A','B','C','D'],
            'A': {'text':'[B] [C] [D]','out':False},
            'B': {'text':'[C]','out':False},
            'C': {'text':'[D]','out':False},
            'D': {'text':'','out':False}
        },
        {
            'taglist':['A','B','C','D','E','F','G'],
            'A': {'text':'[B] [C] [D]','out':False},
            'B': {'text':'[C]','out':False},
            'C': {'text':'[D]','out':False},
            'D': {'text':'','out':False},
            'G': {'text':'[E]','out':True},
            'E': {'text':'[F]','out':True},
            'F': {'text':'[E]','out':True}
        }]
        for emdata,data in enumerate(cases):
            await ctx.send(f"Pass number {emdata}")
            assert is_cyclic_mod(data,'A',{'text':'[B]'})==False
            assert is_cyclic_mod(data,'G',{'text':'[G]'})==True
            for i, v in data.items():
                if i=='taglist': continue
                text=v['text']
                print(i,v)
                result=is_cyclic_i(data,i)
                assert result==v['out']
            await ctx.send("pass complete")
                
              



async def setup(bot):
    await bot.add_cog(Pomelo(bot))

