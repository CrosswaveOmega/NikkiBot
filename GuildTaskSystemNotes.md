
## How to use the TCGuildTask system

1. To use the TCGuildTask system, the task function needs to be defined and added to the Guild_Task_Functions class.  This is done with the `Guild_Task_Functions.add_task_function` method within a `commands.Cog` init method, passing in a unique name and a coroutine defined within the Cog.  This coroutine should take a single argument, a discord.TextMessage object called source_message that is passed to the `execute_task_function` method.

```
def __init__(self, bot:TCBot):
   self.bot=bot
   ...

   Guild_Task_Functions.add_task_function("TASKNAMEHERE",self.gtaskcoroutine)

def cog_unload(self):
   Guild_Task_Functions.remove_task_function("TASKNAMEHERE")


async def gtaskcoroutine(self, source_message:discord.TextMessage):
   #Insert code here.
```
2. These tasks won't run until an admin/moderator for the guild uses a corresponding command that will add an entry to the TCGuildTask table, specifying that they want that task to run within their server at a regular time interval.  The admin/moderator must set specify an **autolog** channel with this command, to both log whenever the bot runs the task (and if there are any errors), and so that the bot can generate a context message in case the guild task runs any of the bot's commands.

3. Upon creation of a TCGuildTask entry, a TCTask object will be added to the bot's TCTaskManager, and will run once the current datetime reaches the datetime specified in the next_run property.

4. The task will run at the specified interval, creating a context message within the server's autolog channel. After the task finishes executing, the next run attribute is calculated based on the task's time interval attribute, and saved to the TCGuildTask table.

##
