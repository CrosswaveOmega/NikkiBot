from datetime import timedelta, timezone, datetime
import json
import discord
import io
import chromadb


class ChromaTools:
    """Class full of static methods for simple Chroma DB ops."""

    @staticmethod
    def get_chroma_client() -> chromadb.ClientAPI:
        '''Create a new chroma client.'''
        client = chromadb.PersistentClient(path="saveData")
        return client
