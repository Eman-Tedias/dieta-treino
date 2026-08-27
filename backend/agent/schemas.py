from pydantic import BaseModel


class HarpyResult(BaseModel):
    """Guarantees the raw output of a harpy .run() call is a plain string."""

    html: str


class QueryResult(BaseModel):
    """Shape check for a query_db result extracted from the raw ToolMessage.

    Does not guarantee the numbers are correct, only that the structure is
    the one query_db is supposed to produce (a real query ran and returned
    columns/rows, not an error dict or something malformed).
    """

    columns: list[str]
    rows: list[list]
