import asyncio
import sys

recoverme=False
def recovery_mode(error):
   '''setup and start the recovery mode bot.'''
   import traceback
   import configparser
   import os
   def setup():
      config = configparser.ConfigParser()
      keys=configparser.ConfigParser()
      if not os.path.exists('keys.ini') or not os.path.exists('config.ini'): return None, None
      else:
         keys.read('keys.ini')
         config.read('config.ini')
         return keys, config
   keys, config=setup()
   if config==None: 
      return
   import discord
   from discord.ext import commands
   import configparser
   import subprocess
   intent=discord.Intents.default();
   intent.presences=True
   intent.message_content=True
   intent.guilds=True
   intent.members=True
   config = configparser.ConfigParser()
   config.read('config.ini')

   token = keys.get("vital", 'cipher')
   eid = config.get("optional", 'error_channel_id')

   recoverbot = commands.Bot(command_prefix='!', intents=intent)

   @recoverbot.event
   async def on_ready():
      print("on.")
      error_channel = await recoverbot.fetch_channel(eid)
      await error_channel.send(f"ALERT! {recoverbot.application.owner.mention}! RECOVERY MODE ACTIVATED.  A FATAL ERROR OCCURED!")
      just_the_string=''.join(traceback.format_exception(None, error, error.__traceback__))
      embed=discord.Embed(title=f"Error: {str(error)}", description=f'```{just_the_string}```')
      embed.set_author(name="Error Details...")
      await error_channel.send(embed=embed)
      await error_channel.send("For the time being, only 3 commands are active: \n !shutdown \n !reboot \n !update.")


   @recoverbot.command()
   async def shutdown(ctx):
      if ctx.author.id!=recoverbot.application.owner.id:
         await ctx.send("INVALID")
         return
      await ctx.send("Shutting down...")
      await recoverbot.close()

   @recoverbot.command()
   async def reboot(ctx):
      global recoverme 
      if ctx.author.id!=recoverbot.application.owner.id:
         await ctx.send("INVALID")
         return
      await ctx.send("attempting recovery...")
      recoverme=True
      await recoverbot.close()

   @recoverbot.command()
   async def update(ctx):
      if ctx.author.id!=recoverbot.application.owner.id:
         await ctx.send("INVALID")
         return
      await ctx.send("Updating...")
      subprocess.Popen(["git", "pull", "-force"])
      await ctx.send("Update complete.")

   recoverbot.run(token)
   return recoverme



if __name__ == "__main__":
   #Run with the bot token as an argument if it's your first time!
   continueme=True
   while continueme:
      continueme=False
      try:
         from pathlib import Path
         Path("/logs").mkdir(parents=True, exist_ok=True) #logs
         from bot import main
         asyncio.run(main(sys.argv))
      except Exception as e:
         continueme=recovery_mode(e)
         print(continueme)

