"""Web base loader class."""
import asyncio
import logging
import re
import warnings
from typing import Any, Dict, Iterator, List, Optional, Union

import aiohttp
import discord
import requests
import assets
from javascript import require, globalThis, eval_js


def is_readable(url):
    timeout=30
    readability= require('@mozilla/readability')
    jsdom=require('jsdom')
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

def read_article_direct(html,url):
    timeout=30
    readability= require('@mozilla/readability')
    jsdom=require('jsdom')
    TurndownService=require('turndown')
    #Is there a better way to do this?
    print('attempting parse')
    out=f'''
    let result=await read_webpage_html_direct(`{html}`,`{url}`,readability,jsdom);
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

async def read_article_aw(html,url):
    now=discord.utils.utcnow()
    getthread=asyncio.to_thread(read_article_direct, url)
    result=await getthread
    print(result)
    text,header=result[0],result[1]
    return text,header


def _build_metadata(soup: Any, url: str) -> dict:
    """Build metadata from BeautifulSoup output."""
    metadata = {"source": url}
    if title := soup.find("title"):
        metadata["title"] = title.get_text()
    if description := soup.find("meta", attrs={"name": "description"}):
        metadata["description"] = description.get("content", "No description found.")
    if html := soup.find("html"):
        metadata["language"] = html.get("lang", "No language found.")
    return metadata


from langchain.docstore.document import Document
import langchain.document_loaders as dl
class ReadableLoader(dl.WebBaseLoader):
    async def scrape_all(self, urls: List[str], parser: Union[str, None] = None) -> List[Any]:
        """Fetch all urls, then return soups for all results."""
        from bs4 import BeautifulSoup

        results = await self.fetch_all(urls)
        final_results = []
        for i, result in enumerate(results):
            url = urls[i]
            
            if parser is None:
                if url.endswith(".xml"):
                    parser = "xml"
                else:
                    parser = self.default_parser
                self._check_parser(parser)
            souped=(BeautifulSoup(result, parser))
            try:
                text,header=await read_article_aw(result,url)
                final_results.append((text,souped))
            except Exception as e:
                text = souped.get_text(**self.bs_get_text_kwargs)
                final_results.append((text,souped))
        return final_results

    def _scrape(self, url: str, parser: Union[str, None] = None) -> Any:
        from bs4 import BeautifulSoup

        if parser is None:
            if url.endswith(".xml"):
                parser = "xml"
            else:
                parser = self.default_parser

        self._check_parser(parser)

        html_doc = self.session.get(url, **self.requests_kwargs)
        if self.raise_for_status:
            html_doc.raise_for_status()
        html_doc.encoding = html_doc.apparent_encoding
        return BeautifulSoup(html_doc.text, parser)

    def scrape(self, parser: Union[str, None] = None) -> Any:
        """Scrape data from webpage and return it in BeautifulSoup format."""

        if parser is None:
            parser = self.default_parser

        return self._scrape(self.web_path, parser)

    def lazy_load(self) -> Iterator[Document]:
        """Lazy load text from the url(s) in web_path."""
        for path in self.web_paths:
            soup = self._scrape(path)
            text = soup.get_text(**self.bs_get_text_kwargs)
            metadata = _build_metadata(soup, path)
            yield Document(page_content=text, metadata=metadata)

    def load(self) -> List[Document]:
        """Load text from the url(s) in web_path."""
        return list(self.lazy_load())

    async def aload(self) -> List[Document]:
        """Load text from the urls in web_path async into Documents."""

        results = await self.scrape_all(self.web_paths)
        docs = []
        for i in range(len(results)):
            text,soup = results[i]
            
            metadata = _build_metadata(soup, self.web_paths[i])
            docs.append(Document(page_content=text, metadata=metadata))

        return docs
