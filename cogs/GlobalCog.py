from typing import List, Dict, Any, Tuple
import discord

# import datetime


from discord.ext import commands

from discord import app_commands
from assets import AssetLookup
from bot import TC_Cog_Mixin, super_context_menu
import cogs.ResearchAgent as ra

from gptmod.chromatools import DocumentScoreVector, ChromaTools
import gptmod.sentence_mem as smem
from utility import WebhookMessageWrapper as web
import gui

import uuid
from langchain.docstore.document import Document

from utility.embed_paginator import pages_of_embeds
from utility.debug import Timer
async def owneronly(interaction: discord.Interaction):
    return await interaction.client.is_owner(interaction.user)


class UserNotes:
    def __init__(self, bot, user):
        # dimensions = 384
        self.userid:int = user.id
        metadata = {"desc": "Simple user note taker.  384 dimensions."}
        self.coll = ChromaTools.get_collection(
            f"usernotes", embed=bot.embedding, path="saveData/usernotes"
        )
        self.shortterm = {}


    async def add_to_mem(
        self,
        ctx: commands.Context,
        content:str,
        key:str='gen',
        topic:str="any"
    ):
        meta = {}
        meta["key"] = key
        meta["foruser"] = self.userid
        meta["topic"] = topic
        meta['value']= content
        meta["date"] = ctx.message.created_at.timestamp()
        meta['split'] = 1
        to_add=f"Topic: {topic}\n: Key:{key}\nContent:{content}"
        doc = Document(page_content=to_add, metadata=meta)
        docs = [doc]
        ids = [
            f"u:{doc.metadata['foruser']},topic:[{doc.metadata['topic']}],key{doc.metadata['key']},sid:[{doc.metadata['split']}]"
            for e, doc in enumerate(docs)
        ]
        if docs:
            self.coll.add_documents(docs, ids)



    async def search_sim(self, content:str) -> Tuple[List[Document],str]:
        persist = "saveData"

        filterwith = {"foruser": self.userid}
        docs =  await self.coll.asimilarity_search_with_score_and_embedding(
               content, k=5, filter=filterwith
            )
        docs2 = (d[0] for d in docs)


        new_output = ""
        tosend=[]
        for source in docs2:
            tosend.append(source)
            if source.page_content:
                content = smem.indent_string(source.page_content.strip(), 1)
                output = f"*{content}\n"
                new_output += output

        return tosend, new_output

    async def delete_note(self, 
        key:str='gen',
        topic:str="any"):
        filterwith = {
            "$and": [
                {"foruser": self.userid},
                {"key": key},
                {'topic':topic},
            ]
        }
        try:
            self.coll._collection.delete(where=filterwith)

            return True
        except ValueError as e:
            gui.dprint(e)
            return False

    async def delete_user_notes(self, userid):
        try:
            self.coll._collection.delete(where={"foruser": userid})

            return True
        except ValueError as e:
            gui.dprint(e)
            return False
        
    async def note_to_embed(self, doc:Document):
        embed=discord.Embed(
            description=f"{doc.metadata['value']}"[:4000]
        )
        embed.add_field(name="topic",value=doc.metadata['topic'][:500])
        
        embed.add_field(name="key",value=doc.metadata['key'][:500])
        return embed




class Global(commands.Cog, TC_Cog_Mixin):
    """General commands"""

    def __init__(self, bot):
        self.helptext = "Some assorted testing commands."
        self.bot = bot
        self.globalonly=True
        self.memehook= AssetLookup.get_asset("memehook",'urls')
        self.usertopics={}
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
        if hasattr(message,'channel'):
            embed.add_field(name="channel",value=f"* {str(message.channel)}, ")
            if hasattr(message.channel, 'parent'):
                embed.add_field(name="parent",value=f"* {str(message.channel.parent)}, ")
            
        await interaction.response.send_message(
            content="Message details below.",
            embed=embed,
        )

    @super_context_menu(name="Repost That Meme",flags='user')
    async def memethief(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        username=interaction.user.display_name
        avatar=str(interaction.user.avatar)
        content=message.content
        embeds=message.embeds

        files=[]
        for a in message.attachments:
            this_file=await a.to_file()
            files.append(this_file)
        await web.postMessageAsWebhookWithURL(self.memehook,
                                              message_content=content,
                                              display_username=username,
                                              avatar_url=avatar,
                                              embed=embeds,file=files)
        await interaction.response.send_message(
            content="Reposted yer meme!",
            ephemeral=True,)

    
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
        """Do a web search"""
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

    @app_commands.command(name="note_topic", description="WIP.  Set your note topic")
    @app_commands.install_types(users=True)
    @app_commands.describe( topic='The topic to add all notes to unless stated otherwise.')
    async def set_topic(self, interaction: discord.Interaction, topic:str) -> None:
        """get bot info for this server"""
        
        ctx: commands.Context = await self.bot.get_context(interaction)
        user=interaction.user
        if not user.id in self.usertopics:
            self.usertopics[user.id]='any'
        self.usertopics[user.id]=topic
        mess=await ctx.send(f"Set your default topic to {topic}.",ephemeral=True)



    @app_commands.command(name="note_add", description="WIP.  Add a quick note using key.")
    @app_commands.install_types(users=True)
    @app_commands.describe(content="Content of your note.",
                           key="The key to save your note under.",
                           topic='The topic for the key to your note under.  Use set topic to change the default one.')
    async def add_note(self, interaction: discord.Interaction, content:str, key:str,topic:str='any') -> None:
        """get bot info for this server"""
        
        ctx: commands.Context = await self.bot.get_context(interaction)
        if topic =='any' and interaction.user.id in self.usertopics:
            topic=self.usertopics[interaction.user.id]
        mess=await ctx.send("<a:LoadingBlue:1206301904863502337> adding note")
        with Timer() as op_timer:
            notes=UserNotes(self.bot,interaction.user)
            await notes.add_to_mem(ctx,content,key[:500],topic[:500])
        await mess.edit(content=f'added note in {op_timer.get_time()} seconds')

    @app_commands.command(name="note_get", description="WIP.  search for a note")
    @app_commands.install_types(users=True)
    @app_commands.describe(content="Content to search",)
    async def get_note(self, interaction: discord.Interaction, content:str )-> None:
        """get 5 notes"""
        
        ctx: commands.Context = await self.bot.get_context(interaction)
        mess=await ctx.send("<a:LoadingBlue:1206301904863502337> getting note")
        with Timer() as op_timer:
            notes=UserNotes(self.bot,interaction.user)
            docs,pc=await notes.search_sim(content)
            embs=[]
            for n in docs:
                print(n)
                emb=await notes.note_to_embed(n)
                embs.append(emb)

        await pages_of_embeds(ctx, embs, ephemeral=True)
        
        await mess.edit(content=f'got notes in {op_timer.get_time()} seconds')

    @app_commands.command(name="note_remove_all", description="Delete all your notes.")
    @app_commands.install_types(users=True)
    @app_commands.describe()
    async def purge_notes(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        
        ctx: commands.Context = await self.bot.get_context(interaction)
        if topic =='any' and interaction.user.id in self.usertopics:
            topic=self.usertopics[interaction.user.id]
        mess=await ctx.send("<a:LoadingBlue:1206301904863502337> deleting all note")
        notes=UserNotes(self.bot,interaction.user)
        await notes.delete_user_notes(interaction.user.id)
        await mess.edit(content='Deleted all your notes.')

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
