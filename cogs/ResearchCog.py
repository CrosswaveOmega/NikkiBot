from typing import Literal
import discord
import operator
import io
import json
import aiohttp
import asyncio
import re
#import datetime
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU

from datetime import datetime, time, timedelta
import time
from queue import Queue

from discord.ext import commands, tasks
from discord.utils import find
from discord import Webhook,ui

from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import MessageTemplates, RRuleView, formatutil, seconds_to_time_string, urltomessage
from utility.embed_paginator import pages_of_embeds
from bot import TCBot,TC_Cog_Mixin, super_context_menu
import purgpt
from database import DatabaseSingleton
from purgpt.functionlib import *
import purgpt.error
from database.database_ai import AuditProfile, ServerAIConfig
#I need the readability npm package to work, so 
from javascript import require, globalThis, eval_js
import assets
import gui
from googleapiclient.discovery import build   #Import the library
def read_article_sync(url):
    readability= require('@mozilla/readability')
    jsdom=require('jsdom')
    TurndownService=require('turndown')
    #Is there a better way to do this?
    print('attempting parse')
    out=f'''
    let result=await read_webpage_plain(`{url}`,readability,jsdom);
    return [result[0],result[1]];
    '''
    myjs=assets.JavascriptLookup.find_javascript_file('readwebpage.js',out)
    #myjs=myjs.replace("URL",url)
    print(myjs)
    rsult= eval_js(myjs)

    output,header=rsult[0],rsult[1]
    simplified_text = output.strip()
    simplified_text = re.sub(r'(\n){4,}', '\n\n\n', simplified_text)
    simplified_text = re.sub(r'\n\n', ' ', simplified_text)
    simplified_text = re.sub(r' {3,}', '  ', simplified_text)
    simplified_text = simplified_text.replace('\t', '')
    simplified_text = re.sub(r'\n+(\s*\n)*', '\n', simplified_text)
    return [simplified_text, header]

async def read_article(url):
    getthread=asyncio.to_thread(read_article_sync, url)
    result=await getthread
    print(result)
    text,header=result[0],result[1]
    return text,header

def extract_masked_links(markdown_text):
    '''just get all masked links.'''
    pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
    matches = re.findall(pattern, markdown_text)
    masked_links = []
    for match in matches:
        link_text, url = match
        masked_links.append((link_text, url))
    
    return masked_links
    
    
class ResearchCog(commands.Cog, TC_Cog_Mixin):
    """For Timers."""
    def __init__(self, bot):
        self.helptext=""
        self.bot=bot
        self.lock=asyncio.Lock()
        self.prompt='''
        Summarize general news articles, forum posts, and wiki pages that have been converted into Markdown. Condense the content into 2-4 medium-length paragraphs with 3-7 sentences per paragraph. Preserve key information and maintain a descriptive tone. The summary should be easily understood by a 10th grader. Exclude any concluding remarks from the summary.
        '''
        self.translationprompt='''
        Given text from a non-English language, provide an accurate English translation, followed by contextual explanations for why and how the text's components conveys that meaning. Organize the explanations in a list format, with each word/phrase/component followed by its corresponding definition and explanation.  Note any double meanings within these explanations.
        '''
        self.init_context_menus()
    @super_context_menu(name="Translate")
    async def translate(self, interaction: discord.Interaction, message: discord.Message) -> None:
            context=await self.bot.get_context(interaction)
            guild=interaction.guild
            user=interaction.user
            
            serverrep,userrep=AuditProfile.get_or_new(guild,user)
            userrep.checktime()
            ok, reason=userrep.check_if_ok()
            if not ok:
                if reason in ['messagelimit','ban']:
                    await context.send("You have exceeded daily rate limit.")
                    return
            userrep.modify_status()
            chat=purgpt.ChatCreation(
                messages=[{'role': "system", 'content':  self.translationprompt }]
            )
            chat.add_message(role='user',content=message.content)

            #Call API
            bot=self.bot

            targetmessage=await context.send(content=f'Translating...')

            res=await bot.gptapi.callapi(chat)
            #await ctx.send(res)
            print(res)
            result=res['choices'][0]['message']['content']
            embeds=[]
            pages=commands.Paginator(prefix='',suffix='',max_size=4024)
            for l in result.split('\n'):
                pages.add_line(l)
            for e, p in enumerate(pages.pages):
                embed=discord.Embed(
                    title=f'Translation' if e==0 else f'Translation {e+1}',
                    description=p
                )
                embeds.append(embed)
           
            await targetmessage.edit(content=message.content,embed=embeds[0])
            for e in embeds[1:]:
                await context.send(embed=e)

    @AILibFunction(name='google_search',
                   description='Get a list of results from a google search query.',
                   enabled=False,
                   force_words=['google','search'],
                   required=['comment'])
    @LibParam(comment='An interesting, amusing remark.',
              query='The query to search google with.',limit="Maximum number of results")
    @commands.command(name='google_search',description='Get a list of results from a google search query.',extras={})
    async def google_search(self,ctx:commands.Context,query:str,comment:str='Search results:',limit:int=5):
        #This is an example of a decorated discord.py command.
        bot=ctx.bot
        if 'google' not in bot.keys or 'cse' not in bot.keys:
            return "insufficient keys!"
        query_service = build(
        "customsearch", 
        "v1", 
        developerKey=bot.keys['google']
        )  
        query_results = query_service.cse().list(
            q=query,    # Query
            cx=bot.keys['cse'],  # CSE ID
            num=limit   
            ).execute()
        results= query_results['items']
        allstr=""
        emb=discord.Embed(title="Search results", description=comment)
        for r in results:
            metatags=r['pagemap']['metatags'][0]
            desc=metatags.get('og:description',"NO DESCRIPTION")
            allstr+=r['link']+"\n"
            emb.add_field(
                name=r['title'][:255],
                value=f"{r['link']}\n{desc}"[:1200],
                inline=False
            )
        returnme=await ctx.send(content=comment,embed=emb)
        return returnme
    @AILibFunction(name='code_gen',
                   description="Output a block of formatted code in accordance with the user's instructions.",
                   required=['comment'], enabled=False
                   )
    @LibParam(comment='An interesting, amusing remark.',code='Formatted computer code in any language to be given to the user.')
    @commands.command(name='codeget',description='generate some code',extras={})
    async def codegen(self,ctx:commands.Context,code:str,comment:str='Search results:'):
        #This is an example of a decorated discord.py command.
        bot=ctx.bot
        emb=discord.Embed(title=comment, description=f"```py\n{code}\n```")
        returnme=await ctx.send(content=comment+"{code[:1024]}",embed=emb)
        return returnme

    @commands.command(name='reader',description="read a website in reader mode, converted to markdown",extras={})
    async def webreader(self,ctx:commands.Context,url:str):
        async with self.lock:
            message=ctx.message
            guild=message.guild
            user=message.author
            article, header=await read_article(url)
            pages=commands.Paginator(prefix='',suffix='')
            for l in article.split('\n'):
                pages.add_line(l)
            await ctx.send(f"# {header}")
            for p in pages.pages:
                await ctx.send(p)
           
    @commands.command(name='summarize',description="make a summary of a url.",extras={})
    async def summarize(self,ctx:commands.Context,url:str):
        async with self.lock:
            message=ctx.message
            guild=message.guild
            user=message.author
            
            serverrep,userrep=AuditProfile.get_or_new(guild,user)
            serverrep.checktime()
            userrep.checktime()


            ok, reason=userrep.check_if_ok()
            if not ok:
                if reason in ['messagelimit','ban']:
                    await ctx.channel.send("You have exceeded daily rate limit.")
                    return
            serverrep.modify_status()
            userrep.modify_status()
            article, header=await read_article(url)
            
            chat=purgpt.ChatCreation(
                messages=[{'role': "system", 'content':  self.prompt }]
            )
            chat.add_message(role='user',content=article)

            #Call API
            bot=ctx.bot
            messageresp=None
            mylinks = extract_masked_links(article)

            async with ctx.channel.typing():
                try:
                    res=await bot.gptapi.callapi(chat)

                    #await ctx.send(res)
                    print(res)
                    result=res['choices'][0]['message']['content']

                    sources=[]
                    for link in mylinks:
                        link_text, url = link
                        link_text=link_text.replace("_","")
                        print(link_text,url)

                        if link_text in result:
                            print(link_text,url)
                            sources.append(f"[{link_text}]({url})")
                            result=result.replace(link_text,f'*{link_text}*')

                    embed=discord.Embed(
                        title=header,
                        description=result[:4028]
                    )
                    name,res='',''
                    for i in sources:
                        if len(res+i)>1020:
                            embed.add_field(
                                name='Sources Located',
                                value=res, inline=False
                            )
                            res=''
                        res+=f"{i}\n"
                    embed.add_field(
                        name='Sources Located',
                        value=res, inline=False
                    )
                    
                    await ctx.send(content=header,embed=embed)
                except Exception as e:
                    return await ctx.send(e)


async def setup(bot):
    await bot.add_cog(ResearchCog(bot))
