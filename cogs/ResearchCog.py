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
from bot import TCBot,TC_Cog_Mixin, StatusEditMessage, super_context_menu
import purgpt
from database import DatabaseSingleton,ServerArchiveProfile
from gptfunctionutil import *
import purgpt.error
from database.database_ai import AuditProfile,ServerAIConfig
#I need the readability npm package to work, so 
from javascript import require, globalThis, eval_js
import assets
import gui
from googleapiclient.discovery import build   #Import the library
from .ArchiveSub import (
  ChannelSep
) 
def is_readable(url):
    readability= require('@mozilla/readability')
    jsdom=require('jsdom', timeout=10000)
    TurndownService=require('turndown')
    #Is there a better way to do this?
    print('attempting parse')
    out=f'''
    let result=await check_read(`{url}`,readability,jsdom);
    return result
    '''
    myjs=assets.JavascriptLookup.find_javascript_file('readwebpage.js',out)
    #myjs=myjs.replace("URL",url)
    print(myjs)
    rsult= eval_js(myjs)
    return rsult

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

async def read_many_articles(urls):
    outputted=[]
    for url in urls:
        getthread=asyncio.to_thread(read_article_sync, url)
        result=await getthread
        print(result)
        text,header=result[0],result[1]
        outputted.append((url,text,header))
    return outputted
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
        self.helptext="This cog is for AI powered websearch and summarization."
        self.bot=bot
        self.lock=asyncio.Lock()
        self.prompt='''
        Summarize general news articles, forum posts, and wiki pages that have been converted into Markdown. Condense the content into 2-4 medium-length paragraphs with 3-7 sentences per paragraph. Preserve key information and maintain a descriptive tone. The summary should be easily understood by a 10th grader. Exclude any concluding remarks from the summary.
        '''
        self.translationprompt='''
        Given text from a non-English language, provide an accurate English translation, followed by contextual explanations for why and how the text's components conveys that meaning. Organize the explanations in a list format, with each word/phrase/component followed by its corresponding definition and explanation.  Note any double meanings within these explanations.
        '''
        self.simpletranslationprompt='''
        Given text from a non-English language, provide an accurate English translation.  If any part of the non-English text can be translated in more than one possible way, provide all possible translations for that part in parenthesis.
        '''
        self.init_context_menus()
    @super_context_menu(name="Translate")
    async def translate(self, interaction: discord.Interaction, message: discord.Message) -> None:
            context=await self.bot.get_context(interaction)
            guild=interaction.guild
            user=interaction.user
            if await context.bot.gptapi.check_oai(context):
                return

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
        'Search google for a query.'
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
        readable_links=[]
        messages=ctx.send("Search completed, indexing.")
        for r in results:
            metatags=r['pagemap']['metatags'][0]
            desc=metatags.get('og:description',"NO DESCRIPTION")
            allstr+=r['link']+"\n"
            emb.add_field(
                name=f"{r['title'][:200]}",
                value=f"{r['link']}\n{desc}"[:1200],
                inline=False
            )
        returnme=await ctx.send(content=comment,embed=emb)
        return returnme
    @AILibFunction(name='google_detective',
                   description='Solve a question using a google search.  Form the query based on the question, and then use the page text from the search results to create an answer..',
                   enabled=False,
                   force_words=['research'],
                   required=['comment','result_limit'])
    @LibParam(comment='An interesting, amusing remark.',
              query='The query to search google with.  Must be related to the question.',
              question='the question that is to be solved with this search.  Must be a complete sentence.',
              result_limit="Number of search results to retrieve.  Minimum of 3,  Maximum of 16.")
    @commands.command(name='google_detective',description='Get a list of results from a google search query.',extras={})
    async def google_detective(self,ctx:commands.Context,question:str,query:str,comment:str='Search results:',result_limit:int=4):
        'Search google for a query.'
        
        bot=ctx.bot
        if 'google' not in bot.keys or 'cse' not in bot.keys:
            return "insufficient keys!"
        query_service = build(
        "customsearch", 
        "v1", 
        developerKey=bot.keys['google']
        ) 
        print(query,question, result_limit)
        query_results = query_service.cse().list(
            q=query,    # Query
            cx=bot.keys['cse'],  # CSE ID
            num=result_limit
            ).execute()
        results= query_results['items']
        allstr=""
        emb=discord.Embed(title="Search results", description=comment)
        all_links=[]
        readable_links=[]
        messages=await ctx.send("Search completed, indexing.")
        lines=''
        for r in results:
            all_links.append(r['link'])
            readable=asyncio.to_thread(is_readable,r['link'])
            if (await readable):
                readable_links.append(r['link'])
                lines="\n".join(readable_links)
                await messages.edit(content=f"{lines}")
        await ctx.send(
            content='drawing conclusion...',
            embed=discord.Embed(\
            title=f'readable links {len(readable_links)}/{len(all_links)}',
            description=f"out=\n{lines}")
            )
        if len(readable_links)>0:
            #Can't use embeddings, so unfortunately I can't use Langchain.
            if ctx.bot.gptapi.openaimode:
                if await ctx.bot.gptapi.check_oai(ctx):
                    return
                

            if True:
                prompt=f'''
    Use the markdown content retrieved from {len(readable_links)} different web pages to answer the question provided to you by the user.  Each of your source web pages will be in their own system messags, and are in the following template:
    BEGIN
    **Name:** [Name Here]
    **Link:** [Link Here]
    **Content:** [Content Here]
    END
    The websites may contradict each other, prioritize information from encyclopedia pages and wikis.  Valid news sources follow.  Annotate your answer with footnotes indicating where you got each piece of information from, and then list those footnote sources at the end of your answer.
    Your answer must be 3-7 medium-length paragraphs with 5-10 sentences per paragraph. Preserve key information from the sources and maintain a descriptive tone. Your goal is not to summarize, your goal is to answer the user's question based on the provided sources.  If there is no information related to the user's question, simply state that you could not find an answer and leave it at that. Exclude any concluding remarks from the answer.
    '''
                
                myout=await read_many_articles(readable_links)
                chat=purgpt.ChatCreation(
                    messages=[{'role': "system", 'content': prompt}],
                    model='gpt-3.5-turbo-16k'
                )
                for line in myout:
                    url,text,header=line
                    myline=f"BEGIN\n**Name:** {header}\n**Link:** {url}\n**Content:** {text}"
                    chat.add_message('system',myline)
                chat.add_message('user',question)
                async with ctx.channel.typing():
                    #Call the API.
                    result=await ctx.bot.gptapi.callapi(chat)
                page=commands.Paginator(prefix='',suffix=None)
                i=result.choices[0]
                role,content=i.message.role,i.message.content
                for p in content.split("\n"):
                    page.add_line(p)
                messageresp=None
                for pa in page.pages:
                    ms=await ctx.channel.send(pa)
                return content
        return "No data"
        
    @commands.hybrid_command(name='translate_simple',description='Translate a block of text.')
    async def translatesimple(self,context,text:str):
            if not context.guild:
                return
            if await context.bot.gptapi.check_oai(context):
                return
            guild,user=context.guild,context.author
            serverrep,userrep=AuditProfile.get_or_new(guild,user)
            userrep.checktime()
            ok, reason=userrep.check_if_ok()
            if not ok:
                if reason in ['messagelimit','ban']:
                    await context.send("You have exceeded daily rate limit.")
                    return
            userrep.modify_status()
            chat=purgpt.ChatCreation(
                messages=[{'role': "system", 'content':  self.simpletranslationprompt }]
            )
            chat.add_message(role='user',content=text)

            #Call API
            bot=self.bot

            targetmessage=await context.send(content=f'Translating...')

            res=await bot.gptapi.callapi(chat)
            #await ctx.send(res)
            print(res)
            result=res['choices'][0]['message']['content']
            embeds=[]
            pages=commands.Paginator(prefix='',suffix='',max_size=2000)
            for l in result.split('\n'):
                pages.add_line(l)
            for e, p in enumerate(pages.pages):
                embed=discord.Embed(
                    title=f'Translation' if e==0 else f'Translation {e+1}',
                    description=p
                )
                embeds.append(embed)
           
            await targetmessage.edit(content=text,embed=embeds[0])
            for e in embeds[1:]:
                await context.send(embed=e)
    
    @AILibFunction(name='code_gen',
                   description="Output a block of formatted code in accordance with the user's instructions.",
                   required=['comment'], enabled=False, force_words=['generate code']
                   )
    @LibParam(comment='An interesting, amusing remark.',code='Formatted computer code in any language to be given to the user.')
    @commands.command(name='code_generate',description='generate some code')
    async def codegen(self,ctx:commands.Context,code:str,comment:str='Search results:'):
        #This is an example of a decorated discord.py command.
        bot=ctx.bot
        emb=discord.Embed(title=comment, description=f"```py\n{code}\n```")
        returnme=await ctx.send(content=comment+"{code[:1024]}",embed=emb)
        return returnme

    @commands.command(name='reader',description="read a website in reader mode, converted to markdown",extras={})
    async def webreader(self,ctx:commands.Context,url:str):
        '''Download the text from a website, and read it'''
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
    @commands.command( extras={"guildtask":['rp_history']})
    async def summarize_day(self, ctx, daystr:str, endstr:str=None):
        """Create a calendar of all archived messages with dates in this channel."""
        bot = ctx.bot
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        
        serverrep,userrep=AuditProfile.get_or_new(guild,ctx.author)
        userrep.checktime()
        ok, reason=userrep.check_if_ok()
        if not ok:
            if reason in ['messagelimit','ban']:
                await ctx.send("I can not process your request.")
                return
        serverrep.modify_status()
        userrep.modify_status()
        profile=ServerArchiveProfile.get_or_new(guildid)
        

        if profile.history_channel_id == 0:
            await MessageTemplates.get_server_archive_embed(ctx,"Set a history channel first.")
            return False
        if channel.id==profile.history_channel_id:
            return False
        archive_channel=guild.get_channel(profile.history_channel_id)
        if archive_channel==None:
            await MessageTemplates.get_server_archive_embed(ctx,"I can't seem to access the history channel, it's gone!")
            return False
        def format_location_name(csep):
            # Replace dashes with spaces
            channel_name=csep.channel
            category=csep.category
            thread=csep.thread
            formatted_name = channel_name.replace('-', ' ')

            # Capitalize the first letter
            formatted_name = formatted_name.capitalize()
            output=f"Location: {formatted_name}, {category}."
            if thread!=None:
                output=f"{output}  {thread}"
            return output
   
        me=await ctx.channel.send(content=f"<a:LetWalk:1118184074239021209> Retrieving archived messages...")
        mt=StatusEditMessage(me,ctx)
        datetime_object = datetime.strptime(f"{daystr} 00:00:00 +0000",'%Y-%m-%d %H:%M:%S %z')
        datetime_object_end=datetime_object
        if endstr:
            datetime_object_end = datetime.strptime(f"{endstr} 00:00:00 +0000",'%Y-%m-%d %H:%M:%S %z')
        se=ChannelSep.get_all_separators_on_date(guildid,datetime_object)
        prompt='''
        You are to summarize a series of chat logs sent across a period of time.
        The log is broken up into segments that start with a message indicating where the conversation took place in, of format:
        'Location: [location name], [location category].  [Optional Sub location].'
        Each message is of format:
        '[character name]: [ContentHere]'
        The Summary's length must reflect the length of the chat log.  A minimum of 2 paragraphs with 5-10 sentences each is required.  
        You must not make overgeneralizations.  You should extract as much key detail as possible while keeping it consise.
        '''
        def get_seps_between_dates(start,end):
            '''this generator returns lists of all separators that are on the specified dates.'''
            cd = start
            print('starting')
            while cd <= end:   
                dc=0
                print(cd)
                se=ChannelSep.get_all_separators_on_date(guildid,cd)
                if se:
                    yield se
                cd += timedelta(days=1)

        script=''''''
        count=ecount=mcount=0
        ecount=0
        await ctx.send('Starting gather.')

        for sep in ChannelSep.get_all_separators_on_dates(guildid, datetime_object,datetime_object_end):
            ecount+=1
            tokens=purgpt.util.num_tokens_from_messages([
                {'role':'system','content':prompt},{
                    'role':'user','content':script}],'gpt-3.5-turbo-16k')
            await mt.editw(min_seconds=15,content=f"<a:LetWalk:1118184074239021209> Currently on Separator {ecount} ({sep.message_count}),message {mcount}.  Tokensize is {tokens}")
            location=format_location_name(sep)
            if tokens> 16384:
                await ctx.send("I'm sorry, but there's too much content on this day for me to summarize.")
                return
            script+="\n"+location+'\n'
            await asyncio.sleep(0.2)
            messages=sep.get_messages()
            await asyncio.sleep(0.5)
            for m in messages:
                count+=1
                mcount+=1
                await asyncio.sleep(0.1)
                if count>5:
                    #To avoid blocking the asyncio loop.
                    
                    tokens=purgpt.util.num_tokens_from_messages([
                    {'role':'system','content':prompt},{
                        'role':'user','content':script}],'gpt-3.5-turbo-16k')
                    await mt.editw(min_seconds=15,content=f"<a:LetWalk:1118184074239021209> Currently on Separator {ecount},message {mcount}.  Tokensize is {tokens}")
                    if tokens> 16384:
                        await ctx.send("I'm sorry, but there's too much content on this day for me to summarize.")
                        return
                    count=0
                embed=m.get_embed()
                if m.content:
                    script=f"{script}\n {m.author}: {m.content}"
                elif embed:
                    embed=embed[0]
                    if embed.type=='rich':
                        embedscript=f"{embed.title}: {embed.description}"
                        script=f"{script}\n {m.author}: {embedscript}"
        chat=purgpt.ChatCreation(
                messages=[{'role': "system", 'content':  prompt }],
                model='gpt-3.5-turbo-16k'
            )
        gui.gprint(script)

        chat.add_message(role='user',content=script)
        tokens=purgpt.util.num_tokens_from_messages(chat.messages,'gpt-3.5-turbo-16k')
        await ctx.send(tokens)
        if tokens> 16384:
            await ctx.send("I'm sorry, but there's too much content on this day for me to summarize.")
            return
        #Call API
        bot=ctx.bot
        messageresp=None

        async with ctx.channel.typing():

            res=await bot.gptapi.callapi(chat)

            #await ctx.send(res)
            print(res)
            if res.get('error',False):
                err=res['error']
                error=purgpt.error.PurGPTError(err,json_body=res)
                raise error
            if res.get('err',False):
                err=res[err]
                error=purgpt.error.PurGPTError(err,json_body=res)
                raise error
            result=res['choices'][0]['message']['content']
            page=commands.Paginator(prefix='',suffix=None,max_size=4000)
            for p in result.split("\n"):
                page.add_line(p)
            messageresp=None
            for pa in page.pages:
                embed=discord.Embed(
                    title='summary',
                    description=pa[:4028]
                )
                ms=await ctx.channel.send(embed=embed)
                
                if messageresp==None:messageresp=ms
    
    @commands.command(name='summarize',description="make a summary of a url.",extras={})
    async def summarize(self,ctx:commands.Context,url:str):
        '''Download the reader mode view of a passed in URL, and summarize it.'''
        async with self.lock:
            message=ctx.message
            guild=message.guild
            user=message.author
            
            if await ctx.bot.gptapi.check_oai(ctx):
                return
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
            article, header=read_article_sync(url)
            
            chat=purgpt.ChatCreation(
                messages=[{'role': "system", 'content':  self.prompt }],
                model='gpt-3.5-turbo-16k'
            )
            chat.add_message(role='user',content=article)
            sources=[]
            
            mylinks = extract_masked_links(article)
            for link in mylinks:
                link_text, url = link
                link_text=link_text.replace("_","")
                print(link_text,url)
                sources.append(f"[{link_text}]({url})")

            #Call API
            bot=ctx.bot
            messageresp=None

            async with ctx.channel.typing():
                try:
                    res=await bot.gptapi.callapi(chat)

                    #await ctx.send(res)
                    print(res)
                    result=res['choices'][0]['message']['content']

                    for link in mylinks:
                        link_text, url = link
                        link_text=link_text.replace("_","")
                        print(link_text,url)
                        if link_text in result:
                            print(link_text,url)
                            #sources.append(f"[{link_text}]({url})")
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
