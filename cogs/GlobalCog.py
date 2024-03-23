from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
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
from utility.mytemplatemessages import MessageTemplates
from .AICalling import AIMessageTemplates
import uuid
from langchain.docstore.document import Document
import datetime
from utility.embed_paginator import pages_of_embeds
from utility.debug import Timer
from database.database_note import NotebookAux

async def owneronly(interaction: discord.Interaction):
    return await interaction.client.is_owner(interaction.user)
topictype=app_commands.Range[str, 2, 128]
keytype=app_commands.Range[str, 2, 128]
contenttype=app_commands.Range[str,5,4096]
class UserNotes:
    def __init__(self, bot, user):
        # dimensions = 384
        self.userid: int = user.id
        metadata = {"desc": "Simple user note taker.  384 dimensions."}
        self.coll = ChromaTools.get_collection(
            f"usernotes_{self.userid}", embed=bot.embedding, path="saveData/usernotes",metadata=metadata
        )
        self.shortterm = {}

    async def add_to_mem(
        self, ctx: commands.Context, content: str, key: str = "gen", topic: str = "any"
    ):
        meta = {}
        meta["key"] = key
        meta["foruser"] = self.userid
        meta["topic"] = topic
        meta["value"] = content
        meta["date"] = ctx.message.created_at.timestamp()
        meta["split"] = 1
        to_add = f"Topic: {topic}\n: Key:{key}\nContent:{content}"
        doc = Document(page_content=to_add, metadata=meta)
        docs = [doc]
        ids = [
            f"u:{doc.metadata['foruser']},topic:[{doc.metadata['topic']}],key[{doc.metadata['key']}],sid:[{doc.metadata['split']}]"
            for e, doc in enumerate(docs)
        ]
        if docs:
            self.coll.add_documents(docs, ids)
            await NotebookAux.add(self.userid,ids[0],key,topic,ctx.message.created_at)
            return doc

    async def search_sim(
        self, content: str, key: Optional[str] = None, topic: Optional[str] = None
    ) -> Tuple[List[Document], str]:
        persist = "saveData"
        filterwith = {"foruser": self.userid}
        conditions = [{"foruser": self.userid}]
        if key:
            conditions.append({"key": key})
        if topic:
            conditions.append({"topic": topic})

        if len(conditions) > 1:
            filterwith = {"$and": conditions}
        docs = await self.coll.asimilarity_search_with_score_and_embedding(
            content, k=5, filter=filterwith
        )
        docs2 = (d[0] for d in docs)

        new_output = ""
        tosend = []
        for source in docs2:
            tosend.append(source)
            print(docs2)
            if source.page_content:
                content = smem.indent_string(source.page_content.strip(), 1)
                output = f"*{content}\n"
                new_output += output
        return tosend, new_output

    async def get_note(self, key: Optional[str] = None, topic: Optional[str] = None):
        filterwith = {"foruser": self.userid}
        conditions = [{"foruser": self.userid}]
        if key:
            conditions.append({"key": key})
        if topic:
            conditions.append({"topic": topic})

        if len(conditions) > 1:
            filterwith = {"$and": conditions}
        try:
            docs = await self.coll.aget(
                where=filterwith, limit=64, include=["documents", "metadatas"]
            )
            print(docs)
            docs2 = smem.results_to_docs(docs)
            return docs2
        except ValueError as e:
            raise e
            return None
    async def get_topics(self):
        filterwith = {"foruser": self.userid}

        try:
            results = await self.coll.aget(
                where=filterwith, include=["metadatas"]
            )
            se=defaultdict(int)
            for m in results["metadatas"]:
                if 'topic' in m:
                    se[m['topic']]+=1
            st=await NotebookAux.list_topic(self.userid)
            print('ste',st)
            return se
        except ValueError as e:
            raise e
            return None

    async def delete_note(self, key: Optional[str] = None, topic: Optional[str] = None):
        filterwith = {"foruser": self.userid}
        conditions = [{"foruser": self.userid}]
        if key:
            conditions.append({"key": key})
        if topic:
            conditions.append({"topic": topic})

        try:
            self.coll._collection.delete(where=filterwith)
            await NotebookAux.remove(self.userid,key,topic)

            return True
        except ValueError as e:
            gui.dprint(e)
            return False

    async def delete_user_notes(self, userid):
        try:
            self.coll.delete_collection()
            await NotebookAux.remove(self.userid)
            return True
        except ValueError as e:
            gui.dprint(e)
            return False

    async def note_to_embed(self, doc: Document):
        embed = discord.Embed(
            description=f"{doc.metadata['value']}"[:4000],
            timestamp=datetime.datetime.fromtimestamp(
                doc.metadata["date"], datetime.timezone.utc
            ),
        )
        embed.add_field(name="topic", value=doc.metadata["topic"][:500])

        embed.add_field(name="key", value=doc.metadata["key"][:500])

        return embed
    
    #async def update_aux(self):



@app_commands.allow_installs(guilds=False, users=True)
class Notes(app_commands.Group, name="notes", description="User Note Commands"):
    pass


class Global(commands.Cog, TC_Cog_Mixin):
    """General commands"""

    def __init__(self, bot):
        self.helptext = "Some assorted testing commands."
        self.bot = bot
        self.globalonly = True
        self.memehook = AssetLookup.get_asset("memehook", "urls")
        self.usertopics = {}
        self.init_context_menus()

    gnote = Notes()

    @super_context_menu(name="Extracool", flags="user")
    async def coooler(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        cont = message.content
        guild = message.guild
        embed = discord.Embed(description=f"It says *{message.content}")
        print(cont, guild, interaction.guild.id)

        if hasattr(message, "author"):
            embed.add_field(
                name="Author", value=f"* {str(message.author)}{type(message.author)}, "
            )

        if hasattr(message, "jump_url"):
            embed.add_field(name="url", value=f"* {str(message.jump_url)}, ")
        if hasattr(message, "channel"):
            embed.add_field(name="channel", value=f"* {str(message.channel)}, ")
            if hasattr(message.channel, "parent"):
                embed.add_field(
                    name="parent", value=f"* {str(message.channel.parent)}, "
                )

        await interaction.response.send_message(
            content="Message details below.",
            ephemeral=True,
            embed=embed,
        )

    @super_context_menu(name="Repost That Meme", flags="user")
    async def memethief(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        username = interaction.user.display_name
        avatar = str(interaction.user.avatar)
        content = message.content
        embeds = message.embeds

        files = []
        for a in message.attachments:
            this_file = await a.to_file()
            files.append(this_file)
        await web.postMessageAsWebhookWithURL(
            self.memehook,
            message_content=content,
            display_username=username,
            avatar_url=avatar,
            embed=embeds,
            file=files,
        )
        await interaction.response.send_message(
            content="Reposted yer meme!",
            ephemeral=True,
        )

    @super_context_menu(name="usercool", flags="user")
    async def coooler2(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        embed = discord.Embed(description=f"This user is {user}")

        await interaction.response.send_message(
            content="User details below.",
            ephemeral=True,
            embed=embed,
        )

    @app_commands.command(name="search", description="search the interwebs.")
    @app_commands.describe(query="Query to search google with.")
    @app_commands.allow_installs(guilds=True, users=True)
    async def websearch(self, interaction: discord.Interaction, query: str) -> None:
        """Do a web search"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        mess = await ctx.send(
            "<a:LoadingBlue:1206301904863502337> Searching", ephemeral=True
        )
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
        await mess.edit(content=None, embed=emb)

    @app_commands.command(name="supersearch", description="use db search.")
    @app_commands.describe(query="Query to search DB for")
    @app_commands.allow_installs(guilds=True, users=True)
    async def doc_talk(self, interaction: discord.Interaction, query: str) -> None:
        """get bot info for this server"""
        owner = await interaction.client.is_owner(interaction.user)
        if not owner:
            await interaction.response.send_message("This command is owner only.")
            return

        ctx: commands.Context = await self.bot.get_context(interaction)
        mess = await ctx.send(
            "<a:LoadingBlue:1206301904863502337> Searching", ephemeral=True
        )
        try:
            ans, source, _ = await ra.actions.research_op(query, 9)
            emb = discord.Embed(description=ans)
            emb.add_field(name="source", value=str(source)[:1000], inline=False)

            audit = await AIMessageTemplates.add_emb_audit(ctx, embed=emb)

            await mess.edit(content=None, embed=emb)
        except Exception as e:
            await ctx.send("something went wrong...")

    @gnote.command(name="set_topic", description="WIP.  Set your note topic")
    @app_commands.describe(
        topic="The topic to add all notes to unless stated otherwise."
    )
    async def set_topic(self, interaction: discord.Interaction, topic: topictype) -> None:
        """get bot info for this server"""

        ctx: commands.Context = await self.bot.get_context(interaction)
        user = interaction.user
        if not user.id in self.usertopics:
            self.usertopics[user.id] = "any"
        self.usertopics[user.id] = topic
        mess = await ctx.send(f"Set your default topic to {topic}.", ephemeral=True)

    @gnote.command(name="add_note", description="WIP.  Add a quick note using key.")
    @app_commands.describe(
        content="Content of your note.",
        key="The key to save your note under.",
        topic="The topic for the key to your note under.  Use set topic to change the default one.",
    )
    async def add_note(
        self,
        interaction: discord.Interaction,
        content: contenttype,
        key: keytype,
        topic: Optional[topictype] = None,
    ) -> None:
        """get bot info for this server"""

        ctx: commands.Context = await self.bot.get_context(interaction)
        if not topic:
            topic = self.usertopics.get(interaction.user.id,'any')
        mess = await ctx.send(
            "<a:LoadingBlue:1206301904863502337> adding note", ephemeral=True
        )
        with Timer() as op_timer:
            notes = UserNotes(self.bot, interaction.user)
            note = await notes.add_to_mem(ctx, content, key[:500], topic[:500])
            emb = await notes.note_to_embed(note)
            await ctx.send(embed=emb, ephemeral=True)
        await mess.edit(content=f"added note in {op_timer.get_time()} seconds")

    @gnote.command(
        name="get_note",
        description="WIP.  Get a note under a key/topic pair, or get all notes for any key or topic.",
    )
    @app_commands.describe(
        key="The key the target note was saved under.",
        topic="The topic for the note.  Use set topic to change the default one.",
    )
    async def get_note(
        self,
        interaction: discord.Interaction,
        key: Optional[keytype] = None,
        topic: Optional[topictype] = None,
    ) -> None:
        """get 5 notes"""

        ctx: commands.Context = await self.bot.get_context(interaction)
        mess = await ctx.send(
            "<a:LoadingBlue:1206301904863502337> getting note", ephemeral=True
        )
        if topic == "any" and interaction.user.id in self.usertopics:
            topic = self.usertopics[interaction.user.id]
        with Timer() as op_timer:
            notes = UserNotes(self.bot, interaction.user)
            docs = await notes.get_note(key, topic)
            embs = []
            for n in docs:
                print(n)
                emb = await notes.note_to_embed(n)
                embs.append(emb)
        await pages_of_embeds(ctx, embs, ephemeral=True)
        await mess.edit(content=f"got notes in {op_timer.get_time()} seconds")

    @gnote.command(
        name="get_topics",
        description="WIP.  Get all of your note topics.",
    )
    async def get_topics(
        self,
        interaction: discord.Interaction,
        
    ) -> None:
        """get 5 notes"""

        ctx: commands.Context = await self.bot.get_context(interaction)
        mess = await ctx.send(
            "<a:LoadingBlue:1206301904863502337> getting topics", ephemeral=True
        )
        with Timer() as op_timer:
            notes = UserNotes(self.bot, interaction.user)
            docs = await notes.get_topics()
            page=commands.Paginator(prefix=None,suffix=None)
            for k, v in docs.items():
                page.add_line(f"{k}:{v}")
            
            embs = []
            for p in page.pages:
                em=discord.Embed(
                    description=p
                )
                embs.append(em)
        await pages_of_embeds(ctx, embs, ephemeral=True)
        await mess.edit(content=f"got topics in {op_timer.get_time()} seconds")
    @gnote.command(name="search_notes", description="WIP.  search for a note")
    @app_commands.describe(
        content="Content to search",
        key="Restrict search to notes with this key.",
        topic="Restrict search to notes with this topic.",
    )
    async def search_note(
        self,
        interaction: discord.Interaction,
        content: contenttype,
        key: Optional[keytype] = None,
        topic: Optional[topictype] = None,
    ) -> None:
        """get 5 notes"""

        ctx: commands.Context = await self.bot.get_context(interaction)
        mess = await ctx.send(
            "<a:LoadingBlue:1206301904863502337> getting note", ephemeral=True
        )
        with Timer() as op_timer:
            notes = UserNotes(self.bot, interaction.user)
            docs, pc = await notes.search_sim(content, key, topic)
            embs = []
            for n in docs:
                print(n)
                emb = await notes.note_to_embed(n)
                embs.append(emb)
        await pages_of_embeds(ctx, embs, ephemeral=True)
        await mess.edit(content=f"got notes in {op_timer.get_time()} seconds")

    @gnote.command(name="purge_all_notes", description="Delete all your notes.")
    @app_commands.describe()
    async def purge_notes(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""

        ctx: commands.Context = await self.bot.get_context(interaction)
        cont,mess=await MessageTemplates.confirm(ctx,"Are you sure you want to delete your notes?",True)
        if not cont:
            await mess.delete()
        mess = await ctx.send("<a:LoadingBlue:1206301904863502337> deleting all note")
        notes = UserNotes(self.bot, interaction.user)
        await notes.delete_user_notes(interaction.user.id)
        await mess.edit(content="Deleted all your notes.")

    @app_commands.command(name="pingtest", description="ping")
    @app_commands.allow_installs(guilds=True, users=True)
    async def ping(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        await interaction.response.send_message("Reading you loud and clear!")

    @app_commands.command(name="context_test", description="ping")
    @app_commands.allow_installs(users=True)
    async def ping2(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        await interaction.response.send_message("Reading you loud and clear!")


async def setup(bot):
    await bot.add_cog(Global(bot))
