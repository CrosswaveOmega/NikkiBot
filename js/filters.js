/*
dependencies:
none

This script is for custom filters for sources
that may require additional logic before 
using the readability library.
*/

class Filter {
  constructor() {
  }

  async trigger(doc, url) {
      // Define the criteria for triggering the action
      throw new Error('not defined');
      
      return false; // Must return a bool value
    }

    async action(doc, url) {
      // Define the action to perform if triggered.
      throw new Error('not defined');
      return {'t':'outputtype', o:{}}; // Must return an object like this.
    }
}


const filters = [];
function addFilterIfNotExists(newFilter) {
  if (!filters.some(filter => filter instanceof newFilter.constructor)) {
    filters.push(new newFilter());
  }
}

async function runthroughfilters(htmldoc,targeturl) {

    let found = false;
    let returntype='NA';
    //return types are all, html, out, and skip
    let output=null;
    for (const filter of filters) {
        if (await filter.trigger(htmldoc, targeturl)) {
            let out= await filter.action(htmldoc, targeturl);
            returntype=out.t;
            output=out.o;
            break; // Execute action for the first triggered filter and stop.
        }
    }
    return {'v': found, 't':returntype,'o':output};
}
module.exports={addFilterIfNotExists,runthroughfilters,Filter}