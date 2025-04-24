release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
web: gunicorn complaints_system.wsgi --bind 0.0.0.0:$PORT --log-file -