from sqlcrucible.conversion.literals import LiteralConverterFactory
from sqlcrucible.conversion.mappings import MappingConverterFactory
from sqlcrucible.conversion.noop import NoOpConverterFactory
from sqlcrucible.conversion.registry import ConverterRegistry
from sqlcrucible.conversion.sequences import SequenceConverterFactory
from sqlcrucible.conversion.unions import UnionConverterFactory

default_registry = ConverterRegistry(
    NoOpConverterFactory(),
    LiteralConverterFactory(),
    SequenceConverterFactory(),
    MappingConverterFactory(),
    UnionConverterFactory(),
)
