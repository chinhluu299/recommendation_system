#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
CSV_DIR = SCRIPT_DIR / "csv"
DB_NAME = "recphones"
NEO4J_USER = "neo4j"
NEO4J_PASS = "1234567890"
BOLT_URI = "bolt://localhost:7687"

DESKTOP_ROOT = Path.home() / "Library/Application Support/neo4j-desktop/Application"
DESKTOP_DBMS_ROOT = DESKTOP_ROOT / "Data/dbmss"
DESKTOP_JRE_ROOT = DESKTOP_ROOT / "Cache/runtime"


def find_dbms() -> Path:
    if not DESKTOP_DBMS_ROOT.exists():
        die(
            f"Không tìm thấy thư mục Neo4j Desktop:\n  {DESKTOP_DBMS_ROOT}\n"
            "Mở Neo4j Desktop ít nhất một lần để khởi tạo."
        )

    candidates = sorted(
        DESKTOP_DBMS_ROOT.glob("dbms-*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        die("Không tìm thấy DBMS nào trong Neo4j Desktop.")

    for dbms in candidates:
        meta = dbms / "relate.dbms.json"
        if meta.exists():
            data = json.loads(meta.read_text())
            dbs = [d["databaseName"] for d in data.get("metadata", {}).get("databases", [])]
            if DB_NAME in dbs:
                return dbms

    return candidates[0]


def find_java_home() -> str | None:
    if not DESKTOP_JRE_ROOT.exists():
        return None

    candidates = sorted(
        DESKTOP_JRE_ROOT.glob("*/zulu-*.jdk/Contents/Home"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return str(candidates[0])

    java_bins = sorted(
        DESKTOP_JRE_ROOT.glob("**/bin/java"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(java_bins[0].parent.parent) if java_bins else None


def make_env(java_home: str | None) -> dict:
    env = os.environ.copy()
    if java_home:
        env["JAVA_HOME"] = java_home
        env["PATH"] = str(Path(java_home) / "bin") + os.pathsep + env.get("PATH", "")
    return env


def run_cypher(cypher_shell: Path, env: dict, query: str,
               database: str = DB_NAME, password: str = NEO4J_PASS) -> bool:
    result = subprocess.run(
        [str(cypher_shell), "-a", BOLT_URI, "-u", NEO4J_USER,
         "-p", password, "-d", database, query],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        print(f"  [WARN] {result.stderr.strip()}")
        return False
    if result.stdout.strip():
        print(f"  {result.stdout.strip()}")
    return True


def run_cypher_file(cypher_shell: Path, env: dict, cypher_file: Path,
                    database: str = DB_NAME, password: str = NEO4J_PASS):
    print(f"  → {cypher_file.name}")
    result = subprocess.run(
        [str(cypher_shell), "-a", BOLT_URI, "-u", NEO4J_USER,
         "-p", password, "-d", database, "--file", str(cypher_file)],
        capture_output=True, text=True, env=env,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if stdout:
        lines = stdout.splitlines()
        for line in lines[:10]:
            print(f"     {line}")
        if len(lines) > 10:
            print(f"     ... ({len(lines) - 10} dòng bị ẩn)")
    if result.returncode != 0:
        die(f"Lỗi khi chạy {cypher_file.name}:\n{stderr}")


def die(msg: str):
    print(f"\n[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def step(n: int, total: int, msg: str):
    print(f"\n[{n}/{total}] {msg}")


def main():
    parser = argparse.ArgumentParser(description="Import Knowledge Graph vào Neo4j Desktop")
    parser.add_argument("--password",     default=NEO4J_PASS,
                        help=f"Neo4j password (default: {NEO4J_PASS})")
    parser.add_argument("--skip-convert", action="store_true",
                        help="Bỏ qua bước convert JSON→CSV (nếu csv/ đã có)")
    parser.add_argument("--wipe",         action="store_true",
                        help="Xoá toàn bộ node/edge cũ trong recphones trước khi import")
    args = parser.parse_args()

    password = args.password
    TOTAL_STEPS = 4 if args.skip_convert else 5

    if not args.skip_convert:
        step(1, TOTAL_STEPS, "Chuyển đổi JSON → CSV...")
        result = subprocess.run([sys.executable, str(SCRIPT_DIR / "convert_to_csv.py")])
        if result.returncode != 0:
            die("convert_to_csv.py thất bại.")

    offset = 0 if args.skip_convert else 1

    step(offset + 1, TOTAL_STEPS, "Tìm DBMS + JRE bundle của Neo4j Desktop...")

    dbms_path = find_dbms()
    cypher_shell = dbms_path / "bin" / "cypher-shell"
    import_dir = dbms_path / "import"
    java_home = find_java_home()
    env = make_env(java_home)

    if not cypher_shell.exists():
        die(f"Không tìm thấy cypher-shell tại:\n  {cypher_shell}")

    print(f"  DBMS         : {dbms_path.name}")
    print(f"  cypher-shell : {cypher_shell}")
    print(f"  JAVA_HOME    : {java_home or '(dùng system Java)'}")
    print(f"  import dir   : {import_dir}")

    step(offset + 2, TOTAL_STEPS, f"Copy CSV → Neo4j import dir...")
    for subdir in ("nodes", "edges"):
        src = CSV_DIR / subdir
        dst = import_dir / subdir
        if not src.exists():
            die(f"Thư mục {src} không tồn tại. Chạy convert_to_csv.py trước.")
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        count = len(list(dst.glob("*.csv")))
        print(f"  ✓ {subdir}/  ({count} files)")

    step(offset + 3, TOTAL_STEPS, f"Kiểm tra / tạo database '{DB_NAME}'...")
    run_cypher(cypher_shell, env,
               f"CREATE DATABASE {DB_NAME} IF NOT EXISTS",
               database="system", password=password)
    run_cypher(cypher_shell, env,
               f"START DATABASE {DB_NAME}",
               database="system", password=password)

    if args.wipe:
        print(f"  [--wipe] Đang xoá toàn bộ dữ liệu cũ trong '{DB_NAME}'...")
        run_cypher(cypher_shell, env,
                   "MATCH (n) CALL { WITH n DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS",
                   database=DB_NAME, password=password)
        print("  ✓ Đã xoá xong.")

    step(offset + 4, TOTAL_STEPS, "Chạy Cypher import scripts...")
    for fname in ("01_constraints.cypher",
                  "02_import_nodes.cypher",
                  "03_import_edges.cypher"):
        run_cypher_file(cypher_shell, env, SCRIPT_DIR / fname,
                        database=DB_NAME, password=password)

    print()
    print(f"Thống kê nodes trong database '{DB_NAME}':")
    run_cypher(
        cypher_shell, env,
        "MATCH (n) RETURN labels(n)[0] AS label, COUNT(n) AS count "
        "ORDER BY count DESC",
        database=DB_NAME, password=password,
    )
    print("\n✓ Hoàn tất!")
    print(f"  Neo4j Browser : http://localhost:7474")
    print(f"  Database      : {DB_NAME}")
    print(f"  User / Pass   : {NEO4J_USER} / {password}")


if __name__ == "__main__":
    main()
