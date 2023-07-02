import inspect
import json
import re
from typing import Any, Coroutine, Dict, List, Union

from enum import Enum, EnumMeta
import discord
from datetime import datetime
from discord.ext import commands, tasks
from discord.ext.commands import Command, Context

class GPTFunctionLibrary:
    """
    A collection of methods to be used with OpenAI's chat completion endpoint.
    When subclassed, decorated methods, called AILibFunctions, will be added to an internal FunctionDict.  
    All methods will be converted to a function schema dictionary, which will be sent to OpenAI along with any user text.
    OpenAI will then format paramaters and return them within a JSON object, which will be used to trigger the method
    with call_by_dict or call_by_dict_ctx for discord.py Bot Commands.
    It's possible to use both subclassed methods and discord.py bot commands, so long as either are decorated with the AILibFunction and LibParam decorators.

    Attributes:
        FunctionDict ( Dict[str, Union[Command,callable]]): A dictionary mapping command and method names to the corresponding Command or methods
    """
    #To Do, make it possible to invoke prefix commands instead.
    CommandDict: Dict[str,Command]={}
    FunctionDict: Dict[str, Union[Command,callable]] = {}
    do_expression: bool = False
    my_math_parser:callable=None
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
    def add_in_commands(self,bot:commands.Bot) -> None:
        """
        Update the FunctionDict with decorated discord.py bot commands.
        """
        for command in bot.walk_commands():
            print(command.qualified_name)
            if "function_schema" in command.extras:
                print(command.qualified_name, command.extras["function_schema"])
                function_name = command.qualified_name
                self.FunctionDict[function_name] = command
    def force_word_check(self,query):
        functions_with_schema = []
        for name, method in self.FunctionDict.items():
            schema=None
            if isinstance(method,Command):
                if method.extras['force_words']:
                    pattern = r'\b(?:{})\b'.format('|'.join(map(re.escape,  method.extras['force_words'])))
                    regex = re.compile(pattern, re.IGNORECASE)
                    match = regex.search(query)

                    if match:
                        schema=method.extras['function_schema']
                        return [schema]
            else:
                if hasattr(method, "function_schema"):
                    if hasattr(method.force_words):
                        pattern = r'\b(?:{})\b'.format('|'.join(map(re.escape,  method.extras['force_words'])))
                        regex = re.compile(pattern, re.IGNORECASE)
                        match = regex.search(query)
                        if method.ai_on==False:
                            continue
                        return [method.function_schema]
        return None
    def get_schema(self) -> List[Dict[str, Any]]:
        """
        Get the list of function schema dictionaries representing callable methods, coroutines, or bot Commands available to the library.

        Returns:
            A list of function schema dictionaries from each decorated method or Command
        """
        functions_with_schema = []
        for name, method in self.FunctionDict.items():
            schema=None
            if isinstance(method,Command):
                if method.extras['ai_on']:
                    schema=method.extras['function_schema']
            else:
                if hasattr(method, "function_schema"):
                    if hasattr(method.ai_on):
                        if method.ai_on==False:
                            continue
                    schema=method.function_schema
            if schema!=None:
                if schema.get('parameters',None)!=None:
                    functions_with_schema.append(schema)
        return functions_with_schema
    def expression_match(self, function_args: str):
        '''because sometimes, the API returns an expression and not a single integer.'''
        if self.do_expression and self.my_math_parser!=None:
            
            expression_detect_pattern = r'(?<=:\s)([^"]*?[+\-*/][^"]*?)(?=(?:,|\s*\}))'
            return re.sub(expression_detect_pattern, lambda m: self.my_math_parser(m.group()), function_args)
        return function_args

    def parse_name_args(self, function_dict):
        print(function_dict)
        function_name = function_dict.get('name')
        function_args = function_dict.get('arguments', None)
        if isinstance(function_args,str):
            #Making it so it won't break on poorly formatted function arguments.
            function_args=function_args.replace("\\n",'\n')
            quoteescapefixpattern = r"(?<=:\s\")(.*?)(?=\"(?:,|\s*\}))"
            #In testing, I once had the API return a poorly escaped function_args attribute
            #That could not be parsed by json.loads, so hence this regex.
            function_args_str=re.sub(quoteescapefixpattern, lambda m: m.group().replace('"', r'\"'), function_args)
            
            function_args_str=self.expression_match(function_args_str)
            print(function_args_str)
            try:
                function_args=json.loads(function_args_str, strict=False)
            except json.JSONDecodeError as e:
                #Something went wrong while parsing, return where.
                output=f"JSONDecodeError: {e.msg} at line {e.lineno} column {e.colno}: `{function_args_str[e.pos]}`"
                raise json.JSONDecodeError(msg=f"{output}\n{function_args_str}", doc=function_args_str,pos=1)
        return function_name,function_args
    def convert_args(self, function_name, function_args):
        method=self.FunctionDict[function_name]
        if isinstance(method,Command):
            schema=method.extras['function_schema']
            parameters=schema['parameters']
            for i, v in parameters['properties'].items():
                if i in function_args:
                    form=v.get('format',None)
                    if not form: continue
                    if form=='date-time':
                        datetime_format = "%Y-%m-%dT%H:%M:%S%z"

                        converted_datetime = datetime.strptime(
                            function_args[i], datetime_format
                            )
                        function_args[i]=converted_datetime
        return function_args


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
        try:
            function_name,function_args=self.parse_name_args(function_dict)
        except Exception as e:
            result=str(e)
            return result
        method = self.FunctionDict.get(function_name)
        if callable(method) and not isinstance(method,(Coroutine,Command)):
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
            The result of the function call, or Done if there is no returned value.
            This is so something can be added to the bot's message_chain.

        Raises:
            AttributeError: If the function name is not found or not callable.
        """
        try:
            function_name,function_args=self.parse_name_args(function_dict)
        except Exception as e:
            result=str(e)
            return result
        print(function_name, function_args,len(function_args))
        method = self.FunctionDict.get(function_name)
        if isinstance(method,Command):
            bot=ctx.bot
            command=bot.get_command(function_name)
            ctx.command=command
            outcome="Done"
            self.convert_args(function_name,function_args)
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
                        outcome2=await ctx.invoke(command,**function_args)
                        if outcome2!=None:
                            outcome=outcome2
                    else:
                        raise commands.CheckFailure('The global check once functions failed.')
                except Exception as exc:
                    bot.dispatch('command_error', ctx, exc)
                else:
                    bot.dispatch('command_completion', ctx)
            elif ctx.invoked_with:
                exc =  commands.CommandNotFound(f'Command "{function_name}" is not found')
                bot.dispatch('command_error', ctx, exc)
            return outcome
            
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
    Decorator to add descriptions to any valid parameter inside a GPTFunctionLibary method or discord.py bot command.
    AILibFunctions without this decorator will not be sent to the AI.
    Args:
        **kwargs: function parameters, and the description to be applied.

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
    'datetime':'string',
    'Literal':'string'
}

def AILibFunction(name: str, description: str, required:List[str]=[],force_words:List[str]=[], enabled=True) -> Any:
    """
    Flags a callable method, Coroutine, or discord.py Command, creating a 
    function schema dictionary to be fed to OpenAI on invocation.
    In the case of a bot Command, the schema is added into the Command.extras attribute.
    Only Commands decorated with this can be called by the AI.

    This should always be above the command decorator:
    @AILibFunction(...)
    @LibParam(...)
    @commands.command(...,extras={})
    Args:
        name (str): The name of the function.
        description (str): The description of the function.
        required:List[str]: list of parameters you want the AI to always use reguardless of if they have defaults.
        force_words:List[str]: list of words that will be used to force this command to be triggered.
        enabled (bool): Whether or not this function is enabled by default.
    Returns:
        callable, Coroutine, or Command.
    """
    def decorator(func: Union[Command,callable,Coroutine]):
        if isinstance(func, Command):
            #Added to the extras dictionary in the Command
            func.is_command=True
            my_schema={}
            my_schema= {
                'name': func.qualified_name,
                'description': description,
                'parameters':None
            }
            if 'parameter_decorators' in func.extras:
                paramdict=func.clean_params
                my_schema.update(
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
                    if oldtypename== 'datetime':
                        param_info['format']='date-time'
                    if oldtypename == 'Literal':
                        #So that Enums can be made.
                        literal_values = param.annotation.__args__
                        param_info['enum'] = literal_values
                    my_schema['parameters']['properties'][param_name] = param_info
                    if param.default == inspect.Parameter.empty or param_name in required:
                        my_schema['parameters']['required'].append(param_name)
            func.extras['function_schema']=my_schema
            func.extras['ai_on']=enabled
            func.extras['force_words']=force_words
            return func
        else:

            wrapper=func
            wrapper.is_command=False
            wrapper.ai_on=enabled
            wrapper.function_schema = {
                'name': name,
                'description': description,
                'parameters':None
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
