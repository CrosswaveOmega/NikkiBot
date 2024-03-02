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
      return {}; // Must return an object
    }
}


const filters = [];
function addFilterIfNotExists(newFilter) {
  if (!filters.some(filter => filter instanceof newFilter.constructor)) {
    filters.push(new newFilter());
  }
}

async function runthroughfilters(htmldoc,targeturl) {

    let outcome = null;
    for (const filter of filters) {
        if (await filter.trigger(htmldoc, targeturl)) {
            outcome = await filter.action(htmldoc, targeturl);
            break; // Execute action for the first triggered filter and stop.
        }
    }
    return {'v': outcome !== null, 'o':outcome};
}
module.exports={addFilterIfNotExists,runthroughfilters,Filter}