print("importing gptmod")
import gptmod.error
from .util import *
from .api import GptmodAPI
from .chat import ChatCreation
from .object import Edit
from .object_core import ApiCore
from .sentence_mem import SentenceMemory, warmup

base_url = None
api_key = None
