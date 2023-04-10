import asyncio
import sys
from bot import main

if __name__ == "__main__":
   #Run with the bot token as an argument if it's your first time!
   asyncio.run(main(sys.argv))
