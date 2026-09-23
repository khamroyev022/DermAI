#!/bin/sh
set -e

echo "Waiting for MySQL at ${MYSQL_HOST:-mysql}:${MYSQL_PORT:-3306} ..."
until python /app/scripts/wait_for_mysql.py; do
  sleep 2
done
echo "MySQL is ready."

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
