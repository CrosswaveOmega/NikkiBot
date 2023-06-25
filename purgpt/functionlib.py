import inspect
import json
from typing import Any, Coroutine, Dict, List, Union

from enum import Enum, EnumMeta
import discord
from discord.ext.commands import Command, Context
class GPTFunctionLibrary:
    """
    A class representing a collection of functions with schema to be used with OpenAI's function calling.

    Attributes:
        FunctionDict (Dict[str, Callable]): A dictionary mapping function names to the corresponding methods.
    """
    #To Do, make it possible to invoke prefix commands instead.
    CommandDict: Dict[str,Command]={}
    FunctionDict: Dict[str, callable] = {}

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        """
        Override the __new__ method to update the FunctionDict when instantiating or subclassing.

        Returns:
            The new instance of the class.
        """
        new_cls = super().__new__(cls, *args, **kwargs)
        new_cls._update_function_dict()
        return new_cls

    def _update_function_dict(self) -> None:
        """
        Update the FunctionDict with decorated methods from the class.

        This method iterates over the class's methods and adds the ones with function schema to the FunctionDict.
        """
        for name, method in self.__class__.__dict__.items():
            if hasattr(method, "function_schema"):
                function_name = method.function_schema['name'] or method.__name__
                self.FunctionDict[function_name] = method
    def add_in_commands(self,bot) -> None:
        """
        Update the FunctionDict with discord commands.
        """
        for command in bot.walk_commands():
            print(command.qualified_name)
            if "function_schema" in command.extras:
                print(command.qualified_name, command.extras["function_schema"])
                function_name = command.qualified_name
                self.FunctionDict[function_name] = command
    def get_schema(self) -> List[Dict[str, Any]]:
        """
        Get the list of function schemas available in the class.

        Returns:
            A list of function schemas.
        """
        functions_with_schema = []
        for name, method in self.FunctionDict.items():
            if isinstance(method,Command):
                functions_with_schema.append(method.extras['function_schema'])
            else:
                if hasattr(method, "function_schema"):
                    functions_with_schema.append(method.function_schema)
        return functions_with_schema

    def call_by_dict(self, function_dict: Dict[str, Any]) -> Any:
        """
        Call a function based on the provided dictionary.

        Args:
            function_dict (Dict[str, Any]): The dictionary containing the function name and arguments.

        Returns:
            The result of the function call.

        Raises:
            AttributeError: If the function name is not found or not callable.
        """
        print(function_dict)
        function_name = function_dict.get('name')
        function_args = function_dict.get('arguments', None)
        if isinstance(function_args,str):
            function_args=json.loads(function_args)
        print(function_name, function_args,len(function_args))
        method = self.FunctionDict.get(function_name)
        if callable(method):
            if len(function_args)>0:
                for i, v in function_args.items():
                    print("st",i,v)
                return method(self, **function_args)
            return method(self)
        else:
            raise AttributeError(f"Method '{function_name}' not found or not callable.")
    
    async def call_by_dict_ctx(self, ctx:Context, function_dict: Dict[str, Any]) -> Coroutine:
        """
        Call a Coroutine or Bot Command based on the provided dictionary.
        Bot Commands must be decorated.

        Args:
            ctx (commands.Context): context object.
            function_dict (Dict[str, Any]): The dictionary containing the function name and arguments.

        Returns:
            The result of the function call.

        Raises:
            AttributeError: If the function name is not found or not callable.
        """
        print(function_dict)
        function_name = function_dict.get('name')
        function_args = function_dict.get('arguments', None)
        if isinstance(function_args,str):
            function_args=json.loads(function_args)
        print(function_name, function_args,len(function_args))
        method = self.FunctionDict.get(function_name)
        if isinstance(method,Command):
            bot=ctx.bot
            command=bot.get_command(function_name)
            ctx.command=command
            if len(function_args)>0:
                for i, v in command.clean_params.items():
                    if not i in function_args:
                        print(i,v)
                        function_args[i]=v.default
                ctx.kwargs=(function_args)
            if ctx.command is not None:
                bot.dispatch('command', ctx)
                try:
                    if await bot.can_run(ctx, call_once=True):
                        await ctx.invoke(command,**function_args)
                    else:
                        raise discord.ext.commands.CheckFailure('The global check once functions failed.')
                except discord.ext.commands.CommandError as exc:
                    await ctx.command.dispatch_error(ctx, exc)
                else:
                    bot.dispatch('command_completion', ctx)
            elif ctx.invoked_with:
                exc =  discord.ext.commands.CommandNotFound(f'Command "{function_name}" is not found')
                bot.dispatch('command_error', ctx, exc)
            return "Done"
            
        else:

            if callable(method):
                if len(function_args)>0:
                    for i, v in function_args.items():
                        print("st",i,v)
                    return await method(self, ctx, **function_args)
                return await method(self,ctx)
            else:
                raise AttributeError(f"Method '{function_name}' not found or not callable.")

def LibParam(**kwargs: Any) -> Any:
    """
    Decorator to add parameter decorators to a function.

    Args:
        **kwargs: The parameter decorators to be added.

    Returns:
        The decorated function.
    """
    def decorator(func: Union[Command,callable]) -> callable:
        if isinstance(func,Command):
            print("Iscommand")
            if not 'parameter_decorators' in func.extras:
                func.extras.setdefault('parameter_decorators',{})
            func.extras['parameter_decorators'].update(kwargs)
            print(func.extras['parameter_decorators'])
            return func
        else:
            if not hasattr(func, "parameter_decorators"):
                func.parameter_decorators = {}
            func.parameter_decorators.update(kwargs)
            return func
    return decorator

substitutions={
    'str':'string',
    'int':'integer',
    'bool':'boolean',
    'float':'number',
    'Literal':'string'
}

def AILibFunction(name: str, description: str, force_words:List[str]=[]) -> Any:
    """
    This decorator can be to add a function_schema element to a regular function, Coroutine, or a 
    discord.py Command object.  In the case of the latter, the schema is added into the
    Command.extras dictionary.

    Args:
        name (str): The name of the function.
        description (str): The description of the function.

    Returns:
        callable, Coroutine, or Command.
    """
    def decorator(func: Union[Command,callable,Coroutine]):
        if isinstance(func, Command):
            func.is_command=True
            func.extras['function_schema'] = {
                'name': func.qualified_name,
                'description': description,
            }
            if 'parameter_decorators' in func.extras:
                paramdict=func.clean_params
                func.extras['function_schema'].update(
                    { 'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                    }}
                )
                for param_name, param in paramdict.items():
                    typename=param.annotation.__name__
                    oldtypename=typename
                    if typename in substitutions:
                        typename=substitutions[typename]
                    else:
                        continue
                    param_info = {
                        'type': typename,
                        'description': func.extras['parameter_decorators'].get(param_name, '')
                    }
                    if oldtypename == 'Literal':
                        #So that Enums can be made.
                        literal_values = param.annotation.__args__
                        param_info['enum'] = literal_values
                    func.extras['function_schema']['parameters']['properties'][param_name] = param_info
                    if param.default == inspect.Parameter.empty:
                        func.extras['function_schema']['parameters']['required'].append(param_name)
            return func
        else:

            wrapper=func
            wrapper.is_command=False
            wrapper.function_schema = {
                'name': name,
                'description': description,
            }
            wrapper.force_words=force_words

            sig = inspect.signature(func)
            if hasattr(func,'parameter_decorators'):
                paramdict=sig.parameters

                wrapper.function_schema.update(
                    { 'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                    }}
                )
                for param_name, param in paramdict.items():
                    typename=param.annotation.__name__
                    oldtypename=typename
                    if typename in substitutions:
                        typename=substitutions[typename]
                    else:
                        continue
                    param_info = {
                        'type': typename,
                        'description': func.parameter_decorators.get(param_name, '')
                    }
                    if typename == '_empty':
                        continue
                    if typename == 'Context':
                        continue
                    if oldtypename == 'Literal':
                        # Extract the literal values from the annotation
                        literal_values = param.annotation.__args__
                        param_info['enum'] = literal_values
                    wrapper.function_schema['parameters']['properties'][param_name] = param_info

                    if param.default == inspect.Parameter.empty:
                        wrapper.function_schema['parameters']['required'].append(param_name)
                return wrapper

    return decorator
