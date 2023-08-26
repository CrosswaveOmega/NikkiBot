
import asyncio
from typing import List, Tuple
from googleapiclient.discovery import build   #Import the library
from javascript import require, globalThis, eval_js
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
from utility import hash_string
import gptmod
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
def read_and_split_link(url:str,chunk_size:int=1024,chunk_overlap:int=1)->List[Document]:
    # Document loader
    loader = webload(url)
    # Index that wraps above steps
    data=loader.load()
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
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=chunk_size,chunk_overlap=chunk_overlap)
    all_splits=text_splitter.split_documents(newdata)
    return all_splits

def store_splits(splits, collection='web_collection'):
    persist='saveData'
    ids = [f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS,doc.metadata['source']))}],sid:[{e}]" for e, doc in enumerate(splits)]
    print(splits)
    print(ids)
    vectorstore=Chroma.from_documents(documents=splits,embedding=OpenAIEmbeddings(),ids=ids,collection_name=collection,persist_directory=persist)
    vectorstore.persist()
def has_url(url,collection='web_collection')->bool:
    persist='saveData'
    vs=Chroma(persist_directory=persist,embedding_function=OpenAIEmbeddings(),collection_name=collection)
    try:
        res=vs._collection_.get(where={'source':url})
        print(res)
        if res: return True
        else: return False
    except Exception as e:
        print(e)
        return False
async def search_sim(question:str,collection='web_collection')-> List[Tuple[Document, float]]:
    persist='saveData'
    vs=Chroma(persist_directory=persist,embedding_function=OpenAIEmbeddings(),collection_name=collection)
    
    docs = await vs.asimilarity_search_with_relevance_scores(question)

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
    print(docs)
    docs2 = sorted(docs, key=lambda x: x[1],reverse=True)
    print(docs2)
    total_tokens=gptmod.util.num_tokens_from_messages([
        {'role':'system','content':prompt},{  'role':'user','content':question}],'gpt-3.5-turbo-16k')
    for doc,score in docs2:
        print(doc)
        meta=doc.metadata#'metadata',{'title':'UNKNOWN','source':'unknown'})
        content=doc.page_content #('page_content','Data lost!')
        output=f'''**Name:** {meta['title']}
        **Link:** {meta['source']}
        **Text:** {content}'''
        formatted_docs.append(output)
        print(output)
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