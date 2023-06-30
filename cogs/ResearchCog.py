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
import gui

async def read_article(url):
    readability= require('@mozilla/readability')
    await asyncio.sleep(1)
    jsdom=require('jsdom')
    await asyncio.sleep(1)
    TurndownService=require('turndown')
    await asyncio.sleep(1)
    #Is there a better way to do this?
    print('attempting parse')
    myjs='''
    var red = readability;
    var ji = jsdom;
    
    function isValidLink(url) {
    // Regular expression pattern to validate URL format
    const urlPattern = /^(ftp|http|https):\/\/[^ "]+$/;
    
    return urlPattern.test(url);
    }
    const targeturl=`URL`
    const response = await fetch(targeturl);
    const html2 = await response.text();
    var doc = new jsdom.JSDOM(html2, {
    url: targeturl
    });
    let reader = new readability.Readability(doc.window.document);
    let article = reader.parse();
    let articleHtml=article.content
    const turndownService = new TurndownService();
    turndownService.addRule('removeInvalidLinks', {
        filter: 'a',
        replacement: (content, node) => {
            const href = node.getAttribute('href');
            if (!href || !isValidLink(href)) {
                return content;
            }
            return href ? `[${content}](${href})` : content;
        }
    });
    const markdownContent = turndownService.turndown(articleHtml);

    return [markdownContent,article.title];

    '''

    myjs=myjs.replace("URL",url)
    print(myjs)
    rsult= eval_js(myjs)
    print(rsult)
    output,header=rsult[0],rsult[1]
    simplified_text = output.strip()
    simplified_text = re.sub(r'(\n){4,}', '\n\n\n', simplified_text)
    simplified_text = re.sub(r'\n\n', ' ', simplified_text)
    simplified_text = re.sub(r' {3,}', '  ', simplified_text)
    simplified_text = simplified_text.replace('\t', '')
    simplified_text = re.sub(r'\n+(\s*\n)*', '\n', simplified_text)
    return simplified_text, header

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
