from pydantic import BaseModel, Field


class HarpyResult(BaseModel):
    """Guarantees the raw output of a harpy .run() call is a plain string."""

    html: str


class GuardrailVerdict(BaseModel):
    """Structured output of the input guardrail classifier.

    Mirrors harpy's GUARDRAIL_SCHEMA (reason + allowed).
    """

    reason: str = Field(description="short explanation for the decision")
    allowed: bool = Field(
        description="true if the text can proceed normally, false if it looks like a manipulation attempt"
    )


class QueryResult(BaseModel):
    """Shape check for a query_db result extracted from the raw ToolMessage.

    Does not guarantee the numbers are correct, only that the structure is
    the one query_db is supposed to produce (a real query ran and returned
    columns/rows, not an error dict or something malformed).
    """

    columns: list[str]
    rows: list[list]
