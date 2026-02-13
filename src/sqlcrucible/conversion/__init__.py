from sqlcrucible.conversion.caching import CachingConverterFactory
from sqlcrucible.conversion.dicts import DictConverterFactory
from sqlcrucible.conversion.literals import LiteralConverterFactory
from sqlcrucible.conversion.noop import NoOpConverterFactory
from sqlcrucible.conversion.registry import ConverterRegistry
from sqlcrucible.conversion.sequences import SequenceConverterFactory
from sqlcrucible.conversion.unions import UnionConverterFactory

default_registry = ConverterRegistry(
    CachingConverterFactory(NoOpConverterFactory()),
    CachingConverterFactory(LiteralConverterFactory()),
    CachingConverterFactory(DictConverterFactory()),
    CachingConverterFactory(SequenceConverterFactory()),
    CachingConverterFactory(UnionConverterFactory()),
)
