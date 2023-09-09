
import asyncio
from typing import List, Tuple
import chromadb
from googleapiclient.discovery import build   #Import the library
from javascriptasync import require, globalThis, eval_js
import assets
import re
import langchain
import langchain.document_loaders as docload
import uuid
import openai
from langchain.docstore.document import Document
webload= docload.WebBaseLoader
from langchain.indexes import VectorstoreIndexCreator
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from .ReadabilityLoader import ReadableLoader
import gptmod

tosplitby=[

    # First, try to split along Markdown headings (starting with level 2)
    "\n#{1,6} ",
    # Note the alternative syntax for headings (below) is not handled here
    # Heading level 2
    # ---------------
    # End of code block
    "```\n",
    # Horizontal lines
    "\n\\*\\*\\*+\n",
    "\n---+\n",
    "\n___+\n",
    " #{1,6} ",
    # Note that this splitter doesn't handle horizontal lines defined
    # by *three or more* of ***, ---, or ___, but this is not handled
    "\n\n",
    "\n",
    " ",
    "",
            
]

def google_search(bot,query:str,result_limit:int):
    query_service = build(
        "customsearch", 
        "v1", 
        developerKey=bot.keys['google']
        ) 
    query_results = query_service.cse().list(
        q=query,    # Query
        cx=bot.keys['cse'],  # CSE ID
        num=result_limit
        ).execute()
    results= query_results['items']
    return results

async def read_and_split_link(url:str,chunk_size:int=1800,chunk_overlap:int=0)->List[Document]:
    # Document loader
    loader = ReadableLoader(url,header_template={
      'User-Agent': 'Mozilla/5.0 (X11,Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
      })
    # Index that wraps above steps
    data=await loader.aload()
    print('ok')
    newdata=[]
    for d in data:
        #Strip excess white space.
        simplified_text = d.page_content.strip()
        simplified_text = re.sub(r'(\n){4,}', '\n\n\n', simplified_text)
        simplified_text = re.sub(r'\n\n', ' ', simplified_text)
        simplified_text = re.sub(r' {3,}', '  ', simplified_text)
        simplified_text = simplified_text.replace('\t', '')
        simplified_text = re.sub(r'\n+(\s*\n)*', '\n', simplified_text)
        d.page_content=simplified_text
        newdata.append(d)
    text_splitter=RecursiveCharacterTextSplitter(separators=tosplitby,chunk_size=chunk_size,chunk_overlap=chunk_overlap)
    all_splits=text_splitter.split_documents(newdata)
    return all_splits

def store_splits(splits, collection='web_collection',client=None):
    persist='saveData'
    ids = [f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS,doc.metadata['source']))}],sid:[{e}]" for e, doc in enumerate(splits)]
    print(splits)
    print(ids)
    if client==None:
        vectorstore=Chroma.from_documents(documents=splits,embedding=OpenAIEmbeddings(),ids=ids,collection_name=collection,persist_directory=persist)
        vectorstore.persist()
    else:
        vectorstore=Chroma.from_documents(documents=splits,embedding=OpenAIEmbeddings(),ids=ids,collection_name=collection,client=client,persist_directory=persist)
        #vectorstore.persist()

def has_url(url,collection='web_collection',client:chromadb.API=None)->bool:
    persist='saveData'
    if client!=None:
        try:
            collectionvar = client.get_collection(collection)
            sres=collectionvar.peek()
            res=collectionvar.get(
                where={"source": url},
                include=['documents','metadatas']
            )
            
            if res.get('ids',None): 
                print('hasres',res)
                return True, res
            return False,None
        except ValueError as e:
            print(e)
            raise e
            return False
    else:

        vs=Chroma(persist_directory=persist,embedding_function=OpenAIEmbeddings(),collection_name=collection,client=client)
        try:
            res=vs._collection_.get(where={'source':url})
            print(res)
            if res: return True
            else: return False
        except Exception as e:
            print(e)
            return False
        
def remove_url(url,collection='web_collection',client:chromadb.API=None)->bool:
    persist='saveData'
    if client!=None:
        try:
            collectionvar = client.get_collection(collection)
            sres=collectionvar.peek()
            res=collectionvar.delete(
                where={"source": url}
            )
            
            return True
        except ValueError as e:
            print(e)
            raise e
            return False
    else:
        return False
async def search_sim(question:str,collection='web_collection',client=None, titleres="None",k=7)-> List[Tuple[Document, float]]:
    persist='saveData'
    vs=Chroma(client=client,persist_directory=persist,embedding_function=OpenAIEmbeddings(),collection_name=collection)
    if titleres=='None':
        docs = await vs.asimilarity_search_with_relevance_scores(question,k=7)

        return docs
    else:
        docs = await vs.asimilarity_search_with_relevance_scores(
            question,
            k=k,
            where={  "$contains":{'title':titleres}}
        )
        return docs

async def format_answer(question:str, docs:List[Tuple[Document, float]])->str:
    prompt='''
    Use the provided sources to answer question provided to you by the user.  Each of your source web pages will be in their own system messags, slimmed down to a series of relevant snippits,
    and are in the following template:
        BEGIN
        **Name:** [Name Here]
        **Link:** [Link Here]
        **Text:** [Text Content Here]
        END
        The websites may contradict each other, prioritize information from encyclopedia pages and wikis.  Valid news sources follow.  
        Your answer must be 3-7 medium-length paragraphs with 5-10 sentences per paragraph. 
        Preserve key information from the sources and maintain a descriptive tone. 
        Your goal is not to summarize, your goal is to answer the user's question based on the provided sources.  
        If there is no information related to the user's question, simply state that you could not find an answer and leave it at that. Exclude any concluding remarks from the answer.

    '''
    formatted_docs=[]
    messages=[
        {"role": "system", "content": prompt},
    ]
    #print(docs)
    
    #print(docs2)
    total_tokens=gptmod.util.num_tokens_from_messages([
        {'role':'system','content':prompt},{  'role':'user','content':question}],'gpt-3.5-turbo-16k')
    for doc,score in docs:
        #print(doc)
        meta=doc.metadata#'metadata',{'title':'UNKNOWN','source':'unknown'})
        content=doc.page_content #('page_content','Data lost!')
        output=f'''**Name:** {meta['title']}
        **Link:** {meta['source']}
        **Text:** {content}'''
        formatted_docs.append(output)
        #print(output)
        tokens=gptmod.util.num_tokens_from_messages([
        {'role':'system','content':output}],'gpt-3.5-turbo-16k')
        
        if total_tokens+tokens>= 14000:
            break
        total_tokens+=tokens
        
        messages.append({'role':'system','content':output})
        if total_tokens>=12000:
            break
    messages.append({'role':'user','content':question})
    completion = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo-16k-0613",
        messages=messages
    )
    return completion.choices[0]['message']['content']