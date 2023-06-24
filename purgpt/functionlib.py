import inspect
import json
from typing import Any, Coroutine, Dict, List

class GPTFunctionLibrary:
    """
    A class representing a collection of functions with schema to be used with OpenAI's function calling.

    Attributes:
        FunctionDict (Dict[str, Callable]): A dictionary mapping function names to the corresponding methods.
    """

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

    def get_schema(self) -> List[Dict[str, Any]]:
        """
        Get the list of function schemas available in the class.

        Returns:
            A list of function schemas.
        """
        functions_with_schema = []
        for name, method in self.__class__.__dict__.items():
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
    
    async def call_by_dict_ctx(self, ctx, function_dict: Dict[str, Any]) -> Coroutine:
        """
        Call a function based on the provided dictionary.

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
        if callable(method):
            if len(function_args)>0:
                for i, v in function_args.items():
                    print("st",i,v)
                return method(self, ctx, **function_args)
            return method(self,ctx)
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
    def decorator(func: callable) -> callable:
        if not hasattr(func, "parameter_decorators"):
            func.parameter_decorators = {}
        func.parameter_decorators.update(kwargs)
        return func
    return decorator

substitutions={
    'str':'string',
    'int':'integer',
    'bool':'boolean'
}

def AILibFunction(name: str, description: str, force_words:List[str]=[]) -> Any:
    """
    Decorator to add function schema to a method.

    Args:
        name (str): The name of the function.
        description (str): The description of the function.

    Returns:
        The decorated method.
    """
    def decorator(func: callable) -> callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper.function_schema = {
            'name': name,
            'description': description,
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': []
            }
        }
        wrapper.force_words=force_words

        sig = inspect.signature(func)
        if hasattr(func,'parameter_decorators'):
            for param_name, param in sig.parameters.items():
                typename=param.annotation.__name__
                if typename in substitutions:
                    typename=substitutions[typename]
                param_info = {
                    'type': typename,
                    'description': func.parameter_decorators.get(param_name, '')
                }
                print(param_name,param_info)
                if typename == '_empty':
                    continue
                if typename == 'Context':
                    continue
                
                wrapper.function_schema['parameters']['properties'][param_name] = param_info

                if param.default == inspect.Parameter.empty:
                    wrapper.function_schema['parameters']['required'].append(param_name)

        return wrapper

    return decorator
