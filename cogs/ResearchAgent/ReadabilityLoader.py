"""Web base loader class."""
import langchain_community.document_loaders as dl
from langchain.docstore.document import Document
import asyncio
import datetime
from io import StringIO
import logging
import re
import warnings
from typing import Any, AsyncGenerator, Dict, Iterator, List, Optional, Tuple, Union
import inspect
import aiohttp
import discord
import requests
import gui
from htmldate import find_date
import assets
from javascriptasync import require, eval_js, eval_js_a
from .metadataenums import MetadataDocType
from bs4 import BeautifulSoup

"""This is a special loader that makes use of Mozilla's readability library."""

from utility import Timer


def remove_links(markdown_text):
    # Regular expression pattern to match masked links
    # pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
    pattern = r"\[([^\]]+)\]\([^)]+\)"

    # Replace the masked links with their text content
    no_links_string = re.sub(pattern, r"\1", markdown_text)

    return no_links_string


async def check_readability(jsenv, html, url):
    myfile = await assets.JavascriptLookup.get_full_pathas(
        "readwebpage.js", "WEBJS", jsenv
    )
    htmls: str = str(html)
    rsult = await myfile.check_read(url, htmls, timeout=45)
    return rsult


async def read_article_direct(jsenv, html, url):
    myfile = await assets.JavascriptLookup.get_full_pathas(
        "readwebpage.js", "WEBJS", jsenv
    )
    timeout = 30

    htmls: str = str(html)

    pythonObject = {"var": htmls, "url": url}

    rsult = await myfile.read_webpage_html_direct(htmls, url, timeout=45)
    output = await rsult.get_a("mark")
    header = await rsult.get_a("orig")
    serial = await header.get_dict_a()

    simplified_text = output.strip()
    simplified_text = re.sub(r"(\n){4,}", "\n\n\n", simplified_text)
    simplified_text = re.sub(r"\n\n", "\n", simplified_text)
    simplified_text = re.sub(r" {3,}", "  ", simplified_text)
    simplified_text = simplified_text.replace("\t", "")
    simplified_text = re.sub(r"\n+(\s*\n)*", "\n", simplified_text)
    return [simplified_text, serial]


async def read_article_aw(jsenv, html, url):
    now = discord.utils.utcnow()
    getthread = await read_article_direct(jsenv, html, url)
    result = getthread
    text, header = result[0], result[1]
    return text, header


def _build_metadata(soup: Any, url: str) -> dict:
    """Build metadata from BeautifulSoup output."""
    metadata = {"source": url}
    if title := soup.find("title"):
        metadata["title"] = title.get_text()
    if description := soup.find("meta", attrs={"name": "description"}):
        metadata["description"] = description.get("content", "No description found.")
    if html := soup.find("html"):
        metadata["language"] = html.get("lang", "No language found.")
    metadata["dateadded"] = datetime.datetime.utcnow().timestamp()
    metadata["date"] = "None"
    try:
        dt = find_date(url)
        if dt:
            metadata["date"] = dt
    except Exception as e:
        gui.dprint(e)
    metadata["reader"] = False
    return metadata


ScrapeResult = Tuple[str, BeautifulSoup, Dict[str, Any]]


class ReadableLoader(dl.WebBaseLoader):
    async def _fetch_with_rate_limit(
        self, url: str, semaphore: asyncio.Semaphore
    ) -> str:
        # Extended from WebBaseLoader so that it will log the errors
        # using this app's logging system.
        async with semaphore:
            try:
                return await self._fetch(url)
            except Exception as e:
                await self.bot.send_error(e, title="fetching a url.", uselog=True)
                if self.continue_on_failure:
                    self.bot.logs.warning(
                        f"Error fetching {url}, skipping due to"
                        f" continue_on_failure=True"
                    )
                    return e
                self.bot.logs.exception(
                    f"Error fetching {url} and aborting, use continue_on_failure=True "
                    "to continue loading urls after encountering an error."
                )
                raise e

    async def scrape_all(
        self, urls: List[Tuple[int, str]], parser: Union[str, None] = None
    ) -> AsyncGenerator[Tuple[int, int, Union[ScrapeResult, Exception]], None]:
        """Fetch all urls, then return soups for all results.
        This function is an asyncronous generator."""

        regular_urls = []

        for e, url in urls:
            regular_urls.append(url)
        with Timer() as timer:
            results = await self.fetch_all(regular_urls)
        elapsed_time = timer.get_time()
        print(f"READ: Took {elapsed_time:.4f} seconds to gather {len(urls)}.")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                yield i, urls[i][0], result
                continue
            url = regular_urls[i]
            if parser is None:
                if url.endswith(".xml"):
                    parser = "xml"
                else:
                    parser = self.default_parser

                self._check_parser(parser)

            souped = BeautifulSoup(result, parser)
            clean_html = re.sub(
                r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "", result
            )
            readable = await check_readability(self.jsenv, clean_html, url)
            if not readable:
                gui.dprint("Not readable link.")
            try:
                with Timer() as timer:
                    text, header = await read_article_aw(self.jsenv, clean_html, url)
                elapsed_time = timer.get_time()
                print(
                    f"READABILITY: Took {elapsed_time:.4f} seconds to convert {urls[i][0]} to readable."
                )
                # YIELD THIS:
                out = (remove_links(text), souped, header)
                yield i, urls[i][0], out

            except Exception as e:
                gui.dprint(e)
                text = souped.get_text(**self.bs_get_text_kwargs)
                # YIELD THIS:
                out = (remove_links(text), souped, None)
                yield i, urls[i][0], out

        # return final_results

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

    async def aload(
        self, bot
    ) -> AsyncGenerator[Tuple[Union[List[Document], Exception], int, int], None]:
        """Load text from the urls in web_path async into Documents."""
        self.jsenv = bot.jsenv
        self.bot = bot
        self.continue_on_failure = True
        docs, typev = [], -1
        # e is the original fetched url position.
        # i is the position in the self.web_paths list.
        # Result is either a tuple or exception.
        async for i, e, result in self.scrape_all(self.web_paths):
            if isinstance(result, Exception):
                yield result, e, -5
            else:
                text, soup, header = result

                metadata = _build_metadata(soup, self.web_paths[i][1])
                typev = MetadataDocType.htmltext

                if not "title" in metadata:
                    metadata["title"] = "No Title"
                if header is not None:
                    if "byline" in header:
                        metadata["authors"] = header["byline"]
                    metadata["website"] = header.get("siteName", "siteunknown")
                    metadata["title"] = header.get("title")
                    typev = MetadataDocType.readertext

                metadata["type"] = int(typev)

                metadata["sum"] = "source"
                yield Document(page_content=text, metadata=metadata), e, typev
