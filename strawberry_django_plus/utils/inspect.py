import functools
import itertools
from typing import Dict, Generator, Optional, Type, TypeVar, Union, cast

from django.db import models
from django.db.models.fields import Field
from django.db.models.fields.reverse_related import ForeignObjectRel
from strawberry.lazy_type import LazyType
from strawberry.type import StrawberryContainer, StrawberryType, StrawberryTypeVar
from strawberry.types.types import TypeDefinition
from strawberry.union import StrawberryUnion
from strawberry.utils.str_converters import to_camel_case
from strawberry_django.fields.types import resolve_model_field_name

try:
    # Try to use the smaller/faster cache decorator if available
    _cache = functools.cache  # type:ignore
except AttributeError:
    _cache = functools.lru_cache

_T = TypeVar("_T")
_R = TypeVar("_R")


@_cache
def get_model_fields(
    model: Type[models.Model],
    *,
    camel_case: bool = False,
    is_input: bool = False,
    is_filter: bool = False,
) -> Dict[str, Union[Field, ForeignObjectRel]]:
    """Get a list of model fields."""
    fields = {}
    for f in model._meta.get_fields():
        name = cast(str, resolve_model_field_name(f, is_input=is_input, is_filter=is_filter))
        if camel_case:
            name = to_camel_case(name)
        fields[name] = f
    return fields


def get_possible_types(
    gql_type: Union[TypeDefinition, StrawberryType, type],
    type_def: Optional[TypeDefinition] = None,
) -> Generator[type, None, None]:
    """Resolve all possible types for gql_type.

    Args:
        gql_type:
            The type to retrieve possibilities from.
        type_def:
            Optional type definition to use to resolve type vars. This is
            mostly used internally, no need to pass this.

    Yields:
        All possibilities for the type

    """
    if isinstance(gql_type, TypeDefinition):
        yield from get_possible_types(gql_type.origin, type_def=gql_type)
    elif isinstance(gql_type, LazyType):
        yield from get_possible_types(gql_type.resolve_type())
    elif isinstance(gql_type, StrawberryTypeVar) and type_def is not None:
        # Try to resolve TypeVar
        for f in type_def.fields:
            f_type = f.type
            if not isinstance(f_type, StrawberryTypeVar):
                continue

            resolved = type_def.type_var_map.get(f_type.type_var, None)
            if resolved is not None:
                yield from get_possible_types(resolved)
    elif isinstance(gql_type, StrawberryContainer):
        yield from get_possible_types(gql_type.of_type)
    elif isinstance(gql_type, StrawberryUnion):
        yield from itertools.chain.from_iterable(
            (get_possible_types(t) for t in gql_type.types),
        )
    elif isinstance(gql_type, StrawberryType):
        # Nothing to return here
        pass
    elif isinstance(gql_type, type):
        yield gql_type


def get_possible_type_definitions(
    gql_type: Union[TypeDefinition, StrawberryType, type]
) -> Generator[TypeDefinition, None, None]:
    """Resolve all possible type definitions for gql_type.

    Args:
        gql_type:
            The type to retrieve possibilities from.

    Yields:
        All possibilities for the type

    """
    if isinstance(gql_type, TypeDefinition):
        yield gql_type
        return

    for t in get_possible_types(gql_type):
        if isinstance(t, TypeDefinition):
            yield t
        elif hasattr(t, "_type_definition"):
            yield t._type_definition  # type:ignore