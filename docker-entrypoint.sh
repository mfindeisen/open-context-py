#!/bin/bash

echo "Create cache table"
/opt/venv/bin/python3 manage.py createcachetable

# Apply database migrations
echo "Apply database migrations"
/opt/venv/bin/python3 manage.py makemigrations versioning profiles fieldgroups inputfields inputrelations rules trinomials uri entity redirects namespaces subjects ocitem manifest assertions events geospace mediafiles documents persons projects strings octypes octypetree predicates predicatetree identifiers obsmetadata editorials ocmysql fields fieldannotations records sources linkannotations linkentities expfields exprecords exptables indexer search staticfiles debug_toolbar django_user_agents 
/opt/venv/bin/python3 manage.py migrate
#python3 manage.py migrate --run-syncdb

# Collect statics
echo "Collect statics"
/opt/venv/bin/python3 manage.py collectstatic --no-input

echo "Start uwsgi"
#uwsgi --emperor /etc/uwsgi/vassals --uid www-data --gid www-data --http-socket :8000 --ini ./ocweb/uwsgi_oc.ini
/opt/venv/bin/uwsgi --ini ./ocweb/uwsgi_oc.ini

tail -f /dev/null
#exec "$@"
