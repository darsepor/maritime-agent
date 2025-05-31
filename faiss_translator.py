from typing import Dict, Tuple, Union

from langchain_core.structured_query import (
    Comparator,
    Comparison,
    Operator,
    Operation,
    StructuredQuery,
    Visitor,
)


class FaissTranslator(Visitor):
    """Translate LangChain StructuredQuery objects into filter dicts that the
    FAISS VectorStore expects.

    The logic is almost identical to the built-in ``ChromaTranslator`` but with a
    small tweak: FAISS' helper ``_create_filter_func`` expects ``$neq`` as the
    *not-equal* operator, whereas the generic comparator enum is ``ne``.

    We therefore map ``Comparator.NE`` → ``"$neq"`` and emit the remaining
    comparators/operators with the usual ``$<name>`` convention (e.g. ``$gt``).
    """

    # Supported logical operators
    allowed_operators = [Operator.AND, Operator.OR, Operator.NOT]

    # Supported comparison operators
    allowed_comparators = [
        Comparator.EQ,
        Comparator.NE,
        Comparator.GT,
        Comparator.GTE,
        Comparator.LT,
        Comparator.LTE,
        Comparator.IN,
        Comparator.NIN,
    ]

    # ---------------------------------------------------------------------
    # Visitor helpers
    # ---------------------------------------------------------------------
    def _format_func(self, func: Union[Operator, Comparator]) -> str:
        """Convert an Operator / Comparator enum to the corresponding key that
        FAISS' metadata filtering understands (e.g. ``$eq``).
        """
        self._validate_func(func)
        # Special-case the NE → $neq naming difference.
        if func == Comparator.NE:
            return "$neq"
        return f"${func.value}"

    # ------------------------------------------------------------------
    # Visitor implementation
    # ------------------------------------------------------------------
    def visit_operation(self, operation: Operation) -> Dict:
        args = [arg.accept(self) for arg in operation.arguments]
        return {self._format_func(operation.operator): args}

    def visit_comparison(self, comparison: Comparison) -> Dict:
        # The query-constructor LLM can sometimes emit complex JSON objects for
        # the value side of the comparison (e.g. relative-date objects like
        # {"months": -12}).  FAISS' built-in filter helpers ultimately pass the
        # value straight into a Python comparison operator (e.g. ge, le), which
        # will raise TypeError if that value is a dict.  We therefore coerce any
        # non-scalar value to a string representation so that the comparison at
        # least remains well-defined (lexicographic for strings).  If you need
        # more sophisticated semantics you could plug in your own filter_func
        # later, but this simple coercion is usually good enough for dates and
        # similar stringable objects.

        def _normalize(v):
            # Scalars are fine.
            if isinstance(v, (str, int, float, bool)):
                return v
            # Datetime → ISO string.
            try:
                import datetime as _dt

                if isinstance(v, (_dt.date, _dt.datetime)):
                    return v.isoformat()
            except Exception:
                pass
            # Fallback: stringify.
            return str(v)

        normalized_value = _normalize(comparison.value)

        return {
            comparison.attribute: {
                self._format_func(comparison.comparator): normalized_value
            }
        }

    def visit_structured_query(
        self, structured_query: StructuredQuery
    ) -> Tuple[str, dict]:
        """Return ``(query, kwargs)`` tuple expected by ``SelfQueryRetriever``.

        ``kwargs`` will contain a ``filter`` key if we have any metadata filter
        logic; otherwise it will be an empty dict.
        """
        if structured_query.filter is None:
            kwargs: Dict = {}
        else:
            kwargs = {"filter": structured_query.filter.accept(self)}
        return structured_query.query, kwargs 