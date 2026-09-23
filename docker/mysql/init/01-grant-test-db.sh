#!/bin/bash
# Runs once when the MySQL data volume is first initialised.
# Lets the application user create/drop the Django test database (test_<name>)
# so `python manage.py test` works inside the backend container.
set -e

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
ALTER DATABASE \`${MYSQL_DATABASE}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON \`test\_${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
SQL
