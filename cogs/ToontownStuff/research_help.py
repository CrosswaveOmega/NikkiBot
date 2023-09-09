import asyncio
from javascriptasync import require, eval_js
import assets
import re

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