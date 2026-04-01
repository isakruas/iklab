"""Example custom tool: SQLite database queries.

Read-only access to SQLite databases in the project.
"""

from __future__ import annotations

import sqlite3

from iklab.tools import mcp
from iklab import sandbox


@mcp.tool(name="SqlQuery")
def sql_query(database: str, query: str) -> str:
    """Execute a read-only SQL query on a SQLite database.

    Args:
        database: path to .db/.sqlite file (relative to workdir)
        query: SQL SELECT query
    """
    # Only allow SELECT queries
    q = query.strip().upper()
    if not q.startswith("SELECT") and not q.startswith("PRAGMA"):
        return "Error: only SELECT and PRAGMA queries are allowed."

    db_path = sandbox.resolve(database)
    if not db_path.is_file():
        return f"Error: database '{database}' not found."

    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA query_only = ON")
        cursor = conn.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(100)
        conn.close()

        if not rows:
            return "(no results)"

        lines = [" | ".join(columns)]
        lines.append("-" * len(lines[0]))
        for row in rows:
            lines.append(" | ".join(str(v) for v in row))
        if len(rows) == 100:
            lines.append("... (limited to 100 rows)")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="SqlTables")
def sql_tables(database: str) -> str:
    """List all tables in a SQLite database."""
    return sql_query(database, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")


TOOL_METADATA = [
    {
        "name": "SqlQuery",
        "category": "context",
        "description": "Execute a read-only SQL query on a SQLite database.",
        "source_module": "tools.database",
    },
    {
        "name": "SqlTables",
        "category": "context",
        "description": "List all tables in a SQLite database.",
        "source_module": "tools.database",
    },
]
