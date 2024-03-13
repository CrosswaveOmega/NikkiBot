/*
dependencies:
@mozilla/readability
happy-dom
turndown

This script is for taking in a single url, reading the html from that site,
and then running that html through the Readability package to get readable content
from that site.

This script is intended to be used in conjunction with JsPyBridgeAsync.

INTENDED TO BE EXECUTED THROUGH JsPyBridgeAsync!
*/
const {isProbablyReaderable, Readability}=require('@mozilla/readability')
const {Window}=require('happy-dom')
const {runthroughfilters}=require('./filters.js')
const {load_filters}=require('./custom_filters.js')
const TurndownService=require('turndown')
var turndownService=new TurndownService({ 'headingStyle': 'atx' });
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
settings={
  disableJavaScriptEvaluation: true,
			disableJavaScriptFileLoading: true,
			disableCSSFileLoading: true,
			disableIframePageLoading: true,
			disableComputedStyleRendering: true,
			disableErrorCapturing: false,
			enableFileSystemHttpRequests: false,
			navigator: {
				userAgent: `Mozilla/5.0 (X11; ${
					process.platform.charAt(0).toUpperCase() + process.platform.slice(1) + ' ' + process.arch
				}) AppleWebKit/537.36 (KHTML, like Gecko) HappyDOM/${5}`
			},
			device: {
				prefersColorScheme: 'light',
				mediaType: 'screen'
			}
}
var core={};
function isValidLink(url) {
  // Regular expression pattern to validate URL format
  const urlPattern = /^(ftp|http|https):\/\/[^ "]+$/;

  return urlPattern.test(url);
}


load_filters();

async function setup(){
  

  core.ts=new TurndownService({ 'headingStyle': 'atx' });    
  core.ts.addRule('removeInvalidLinks', {
      filter: 'a',
      replacement: (content, node) => {
        const href = node.getAttribute('href');
        if (!href || !isValidLink(href)) {
          return content;
        }
        return href ? `[${content}](${href})` : content;
      }
    });
}
async function check_read(targeturl,html_use = null) {
  let html2;
  if (!html_use) {
    const response = await fetch(targeturl);
    html2 = await response.text();
  } else {
    html2 = html_use;
  }
  const window = new Window({
    innerWidth: 1024,
    innerHeight: 768,
    url: targeturl,
    settings:settings
  });
  window.document.write(html2)


  var outcome= isProbablyReaderable(window.document)
  window.happyDOM.cancelAsync()
  return outcome
}

async function read_webpage_plain(targeturl) {

    function isValidLink(url) {
      // Regular expression pattern to validate URL format
      const urlPattern = /^(ftp|http|https):\/\/[^ "]+$/;

      return urlPattern.test(url);
    }
    
    let html2="";
    let article={};
    let articleHtml='';
    let markdownContent='';
    let c=await runthroughfilters('',targeturl);
    console.log(c.t);
    if (c.t=='skip'){
      return {'mark':'bad link', 'orig':article};
    }
    if (c.t=='all'){
      markdownContent=c.o.mark;
      article=c.o.article;
      return {'mark':markdownContent, 'orig':article};
    }
    if (c.t == 'html') {
      //No need to fetch, the html is here.
      html2 = c['o'];
    }
    if (c.v != true) { //no reason to fetch.
      const response = await fetch(targeturl);
      html2 = await response.text();
    }
    if (c.t!='htmlout'){
      const window = new Window({
        innerWidth: 1024,
        innerHeight: 768,
        url: targeturl,
        settings:settings
      });

      window.document.write(html2)


      
      let reader = new Readability(window.document);
      article = reader.parse();
      articleHtml = article.content;
      window.happyDOM.cancelAsync()
    }
    else{
      article=c.o.article;
      articleHtml=c.o.articleHtml;
    }

    markdownContent = turndownService.turndown(articleHtml);
    return {'mark':markdownContent, 'orig':article};
  }

 async function read_webpage_html_direct(htmldoc,targeturl) {
  console.log(targeturl);
  let html2=htmldoc;
  let article={};
  let articleHtml='';
  let markdownContent='';
    let c=await runthroughfilters(htmldoc,targeturl);
    console.log(c.t);
    if (c.t=='skip'){
      return {'mark':'bad link', 'orig':article};
    }
    if(c.t=='all'){
      return c['o'];
    }

    function isValidLink(url) {
      // Regular expression pattern to validate URL format
      const urlPattern = /^(ftp|http|https):\/\/[^ "]+$/;

      return urlPattern.test(url);
    }
    console.log(c.t);
    if (c.t!='htmlout'){

      const window = new Window({
        innerWidth: 1024,
        innerHeight: 768,
        url: targeturl,
        settings:settings
      });

      window.document.write(html2);


      
      let reader = new Readability(window.document);

      article = reader.parse();
      articleHtml = article.content;
      window.happyDOM.cancelAsync();
    }
    else{
      article=c.o.article;
      articleHtml=c.o.articleHtml;
    }
    markdownContent = turndownService.turndown(articleHtml);
    return  {'mark':markdownContent, 'orig':article};
}
module.exports={setup, check_read,read_webpage_plain,read_webpage_html_direct}