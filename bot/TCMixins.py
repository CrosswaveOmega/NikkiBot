import gui
import inspect
import discord
from discord.app_commands import ContextMenu, locale_str
import random
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)

MISSING: Any = discord.utils.MISSING


ctx_comms = {}


class NonContextMenu:

    """
    A simple class that stores initalization parameters for ContextMenus in cogs.

    Attributes
    ------------

    callname: :class:`str`
            The name of the function in the cog that will be initalized as the
            Context Menu's callback.  This is also the key in the self.ctx_menus dictionary.
    initalizer: :class:`dict`
            A dictionary that stores the other initalization parameters for
            the context menu.
            name: :class:`str`
                The name of the context menu.
            nsfw: :class:`bool`
                Whether the command is NSFW and should only work in NSFW channels.
                Defaults to ``False``.
            auto_locale_strings: :class: bool
            extras: :class:`dict`
                A dictionary that can be used to store extraneous data.
                The library will not touch any values or keys within this dictionary."""

    def __init__(
        self,
        *,
        name,
        callback: str,
        nsfw: bool = False,
        auto_locale_strings: bool = True,
        flags=None,
        extras: Dict[Any, Any] = MISSING,
    ):
        self.callname = callback
        self.flags = flags
        self.initalizer = {
            "name": name,
            "nsfw": nsfw,
            "auto_locale_strings": auto_locale_strings,
            "extras": extras,
            "allowed_installs": flags,
        }

    def __repr__(self):
        return str(self.initalizer)


class TC_Cog_Mixin:
    """
    A mixin to define additional functions, including the the ability to add on
    context menus via decorator inside a cog.
    """

    def __init__(self):
        self.ctx_menus = {}

    def server_profile_field_ext(self, guild: discord.Guild) -> Dict[str, Any]:
        """returns a dictionary that represents a single discord embed field
        with 3 key/value pairs:  name:str.  value:str.  inline:boolean"""
        return {}

    def init_context_menus(self):
        """Initalize context menus for this cog specified added via the @super_context_menu decorator.
        All Context Menus will be added to the self.ctx_menus dictionary added to the cog by this function.
        """
        name = self.__class__.__name__
        # Check if the cog's class name is inside the ctx_comms dict
        if name in ctx_comms:
            self.ctx_menus = {}
            for v in ctx_comms[name]:
                if not v.callname in self.ctx_menus:
                    # Check if the cog has a function by the name of
                    # v.callname
                    if hasattr(self, v.callname):
                        caller = getattr(self, v.callname)
                        cmenu = ContextMenu(
                            callback=caller,
                            **v.initalizer,
                        )
                        self.add_context_menu(v.callname, cmenu)

    def add_context_menu(self, name: str, ctx_menu: ContextMenu):
        """add a context menu with name to the ctx_menus dictionary."""
        self.ctx_menus[name] = ctx_menu

    def remove_context_menus(self):
        self.ctx_menus = {}


# @super_context_menu
def super_context_menu(
    *,
    name: Union[str, locale_str] = MISSING,
    nsfw: bool = False,
    auto_locale_strings: bool = True,
    extras: Dict[Any, Any] = MISSING,
    flags=None,
):
    """Because I can't define a ContextMenu inside a class, this decorator makes a psuedo
    Context menu to store the initalization parameters, and stores that into a global dictionary
    `ctx_comms` which is then initalized into the loaded in command.Cogs object.
    This is to make development of context menu commands easier.
    Used in the same way as @app_commands.context_menu()

    Examples
    ---------

    .. code-block:: python3

        @super_context_menu()
        async def react(self, interaction: discord.Interaction, message: discord.Message):
            await interaction.response.send_message('Very cool message!', ephemeral=True)

        @super_context_menu()
        async def ban(self, interaction: discord.Interaction, user: discord.Member):
            await interaction.response.send_message(f'Should I actually ban {user}...', ephemeral=True)

    Parameters (same as @app_commands.context_menu)
    ------------
    name: :class:`str`
        The name of the context menu command. If not given, it defaults to a title-case
        version of the callback name. Note that unlike regular slash commands this can
        have spaces and upper case characters in the name.
    nsfw: :class:`bool`
        Whether the command is NSFW and should only work in NSFW channels. Defaults to ``False``.
        Due to a Discord limitation, this does not work on subcommands.
    auto_locale_strings: :class:`bool`
        If this is set to ``True``, then all translatable strings will implicitly
        be wrapped into :class:`locale_str` rather than :class:`str`. This could
        avoid some repetition and be more ergonomic for certain defaults such
        as default command names, command descriptions, and parameter names.
        Defaults to ``True``.
    extras: :class:`dict`
        A dictionary that can be used to store extraneous data.
        The library will not touch any values or keys within this dictionary.
    """

    def decorator(func):
        if not inspect.iscoroutinefunction(func):
            raise TypeError("context menu function must be a coroutine function")

        cls_name = func.__qualname__.split(".")[0]  # Get the name of the class
        # Add class entry to ctx_comms if needed.
        if cls_name not in ctx_comms:
            ctx_comms[cls_name] = []
        functionname = func.__name__
        actual_name = functionname.title() if name is MISSING else name
        uflags = discord.flags.AppInstallationType.none()
        uflags.guild_install = True
        uflags.user_install = False
        if flags == "user":
            uflags = discord.flags.AppInstallationType.none()
            uflags.user_install = True
            uflags.guild_install = False
        ctx_menu = NonContextMenu(
            name=actual_name,
            nsfw=nsfw,
            callback=functionname,
            auto_locale_strings=auto_locale_strings,
            flags=uflags,
            extras=extras,
        )
        # Add the Not Context menu to ctx_comms
        ctx_comms[cls_name].append(ctx_menu)
        return func

    return decorator


class CogFieldList:
    """This is mixed into the TCBot object so that it may get a list of fields."""

    def get_field_list(self, guild: discord.Guild) -> List[Dict[str, Any]]:
        """returns a list of dictionaries that represents a single discord embed field
        with 3 key/value pairs:  name:str.  value:str.  inline:boolean"""
        cogs_list = self.cogs.values()
        extended_fields = []
        # Add extended fields
        for cog in cogs_list:
            if hasattr(cog, "server_profile_field_ext") and callable(
                getattr(cog, "server_profile_field_ext")
            ):
                res = cog.server_profile_field_ext(guild)
                if res:
                    extended_fields.append(res)
                gui.gprint(
                    f"{cog.__class__.__name__} has the function 'server_profile_fieldext'"
                )
            else:
                pass
        return extended_fields


class StatusTicker:
    """Mixin that provides rotating bot statuses."""

    status_map, status_queue = {}, []

    def add_act(
        self,
        key: str,
        value: str,
        activity_type: discord.ActivityType = discord.ActivityType.playing,
    ):
        """Add an activity to the status map.
        Args:
            key (str): Key of status.
            value (str): status to be displayed.
            activity_type (discord.ActivityType, optional): The type of status to be displayed.
        """
        activity = discord.Activity(type=activity_type, name=value)
        self.status_map[key] = activity

    def remove_act(self, key):
        """Add an activity to the status map.
        Args:
            key (str): Key of status.
            value (str): status to be displayed.
            activity_type (discord.ActivityType, optional): The type of status to be displayed.
        """
        if key in self.status_map:
            self.status_map.pop(key)

    async def status_ticker_next(self):
        """select the next relevant status element."""
        if self.status_map:
            if not self.status_queue:
                self.status_queue = list(self.status_map.keys())
                random.shuffle(self.status_queue)
            cont = True
            while cont and len(self.status_queue) >= 1:
                cont = False
                if len(self.status_queue) >= 1:
                    key = self.status_queue.pop(0)
                    if key in self.status_map:
                        status = self.status_map[key]
                        await self.change_presence(activity=status)
                    else:
                        cont = True
