
from typing import List, Optional, Type, TypeVar


from ..models import *
from ..models.ABC.model import BaseApiModel

T = TypeVar("T", bound=BaseApiModel)

def make_output(
    data: Any, model: Type[T], index: Optional[int] = None
) -> Union[Any, List[Any]]:
    """
    Process the API response data based on the model type and index.

    Args:
        data (Any): The raw API response data.
        model (Type[T]): The model class to instantiate.
        index (Optional[int]): An optional index for single-item responses.

    Returns:
        Union[Any, List[Any]]: The processed model instance(s).
    """

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    if index is not None:
        if isinstance(data, dict) and data or isinstance(data, list) and data:
            mod = model(**(data if isinstance(data, dict) else data[0]))
            mod.retrieved_at = now
            return mod
        return model()
    else:
        if isinstance(data, list):
            return [model(**item, retrieved_at=now) for item in data] if data else []
        elif isinstance(data, dict) and data:
            mod = model(**data)
            mod.retrieved_at = now
            return mod
        return {}

