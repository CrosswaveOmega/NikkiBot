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
const Readability=require('@mozilla/readability')
const {Window}=require('happy-dom')
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

async function setup(mod1, mod2, mod3){
  

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

async function check_read(targeturl) {





  const response = await fetch(targeturl);
  const html2 = await response.text();
  const window = new Window({
    innerWidth: 1024,
    innerHeight: 768,
    url: 'http://localhost:8080',
    settings:settings
  });
  console.log("clear b")
  window.document.write(html2)
  console.log(html2)
  console.log('clear c')
  
  var outcome= Readability.isProbablyReaderable(window.document)
  window.happyDOM.cancelAsync()
  return outcome
}

async function read_webpage_plain(targeturl) {

    function isValidLink(url) {
      // Regular expression pattern to validate URL format
      const urlPattern = /^(ftp|http|https):\/\/[^ "]+$/;

      return urlPattern.test(url);
    }
    console.log("clear A")
    const response = await fetch(targeturl);
    const html2 = await response.text();
    const window = new Window({
      innerWidth: 1024,
      innerHeight: 768,
      url: 'http://localhost:8080',
      settings:settings
    });
    console.log("clear b")
    window.document.write(html2)
    console.log(html2)
    console.log('clear c')
    
    let reader = new Readability.Readability(window.document);
    let article = reader.parse();
    let articleHtml = article.content;
    window.happyDOM.cancelAsync()
    

    const markdownContent = turndownService.turndown(articleHtml);
    return {'mark':markdownContent, 'orig':article};
  }

 async function read_webpage_html_direct(htmldoc,targeturl) {


    function isValidLink(url) {
      // Regular expression pattern to validate URL format
      const urlPattern = /^(ftp|http|https):\/\/[^ "]+$/;

      return urlPattern.test(url);
    }

    const html2 = htmldoc
    const window = new Window({
      innerWidth: 1024,
      innerHeight: 768,
      url: 'http://localhost:8080',
      settings:settings
    });

    window.document.write(html2)
    console.log(html2)
    console.log('clear c')
    let reader = new Readability.Readability(window.document);
    let article = reader.parse();
    let articleHtml = article.content;
    //The heading style recognized by discord apps.
    window.happyDOM.cancelAsync()
    const markdownContent = turndownService.turndown(articleHtml);
    return  {'mark':markdownContent, 'orig':article};
}
module.exports={setup, check_read,read_webpage_plain,read_webpage_html_direct}