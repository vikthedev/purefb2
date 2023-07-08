# pylint: disable=invalid-name

from Lib.typus.core import TypusCore
from Lib.typus.processors import (
    EnQuotes,
    EnRuExpressions,
    EscapeHtml,
    EscapePhrases,
    RuQuotes,
)


class EnTypus(TypusCore):
    processors = (
        EscapePhrases,
        EscapeHtml,
        EnQuotes,
        EnRuExpressions,
    )


class RuTypus(TypusCore):
    processors = (
        EscapePhrases,
        EscapeHtml,
        RuQuotes,
        EnRuExpressions,
    )


en_typus, ru_typus = EnTypus(), RuTypus()
