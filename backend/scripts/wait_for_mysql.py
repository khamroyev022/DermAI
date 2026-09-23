"""Exit 0 when MySQL accepts connections with the configured credentials, else 1."""

import os
import sys

import MySQLdb

try:
    MySQLdb.connect(
        host=os.getenv("MYSQL_HOST", "mysql"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "bookai"),
        passwd=os.getenv("MYSQL_PASSWORD", ""),
        db=os.getenv("MYSQL_DATABASE", "bookai"),
    ).close()
except Exception as exc:  # noqa: BLE001
    print(f"  not ready: {exc}")
    sys.exit(1)
