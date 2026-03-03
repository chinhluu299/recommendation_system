"""
graph_search.py
Kết nối Neo4j, thực thi Cypher query, trả về kết quả dạng list[dict].
"""

from contextlib import contextmanager
from neo4j import GraphDatabase
from neo4j.exceptions import CypherSyntaxError, ServiceUnavailable

# ─── Config ───────────────────────────────────────────────────────────────────

NEO4J_URI  = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "1234567890"
NEO4J_DB   = "recphones"

# ─── Driver (singleton) ───────────────────────────────────────────────────────

_driver = None

def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASS),
        )
    return _driver


def close():
    """Đóng kết nối — gọi khi tắt app."""
    global _driver
    if _driver:
        _driver.close()
        _driver = None


# ─── Query runner ─────────────────────────────────────────────────────────────

def run_query(cypher: str, params: dict = None) -> list[dict]:
    """
    Thực thi Cypher query trên database recphones.

    Returns:
        List các record dạng dict.

    Raises:
        ConnectionError  : Neo4j chưa khởi động hoặc sai URI
        SyntaxError      : Cypher không hợp lệ
        RuntimeError     : Lỗi khác từ Neo4j
    """
    try:
        driver = _get_driver()
        with driver.session(database=NEO4J_DB) as session:
            result = session.run(cypher, params or {})
            records = [dict(record) for record in result]
            return records

    except ServiceUnavailable as e:
        raise ConnectionError(
            f"Không thể kết nối Neo4j tại {NEO4J_URI}.\n"
            "Hãy đảm bảo Neo4j Desktop đang chạy."
        ) from e

    except CypherSyntaxError as e:
        raise SyntaxError(f"Cypher không hợp lệ:\n{e.message}") from e

    except Exception as e:
        raise RuntimeError(f"Lỗi Neo4j: {e}") from e


def test_connection() -> bool:
    """Kiểm tra kết nối và database recphones có tồn tại không."""
    try:
        rows = run_query("RETURN 1 AS ok")
        return rows[0]["ok"] == 1
    except Exception:
        return False


def count_nodes() -> dict:
    """Trả về thống kê số node theo từng label."""
    rows = run_query(
        "MATCH (n) RETURN labels(n)[0] AS label, COUNT(n) AS count "
        "ORDER BY count DESC"
    )
    return {r["label"]: r["count"] for r in rows}


def run_vector_query(
    cypher: str,
    query_embedding: list[float],
    extra_params: dict | None = None,
) -> list[dict]:
    """
    Thực thi Cypher query có sử dụng Neo4j vector index.
    Truyền query_embedding vào params $query_embedding.

    Args:
        cypher          : Cypher string với $query_embedding placeholder
        query_embedding : Vector embedding của câu query (list[float])
        extra_params    : Các params bổ sung nếu cần

    Returns:
        List records dạng dict.
    """
    params = {"query_embedding": query_embedding}
    if extra_params:
        params.update(extra_params)
    return run_query(cypher, params)
