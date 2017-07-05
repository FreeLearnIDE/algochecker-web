## Installation guide ##
Recommended: latest Ubuntu LTS.

1. Install **PostgreSQL** database backend (`apt-get install postgresql`).
2. Configure some user and database in PostgreSQL:
https://www.cyberciti.biz/faq/howto-add-postgresql-user-account/
3. Install **Redis** message queue, may be with default settings (`apt-get install redis-server`).
4. Copy `algoweb/settings.py.dist` into `algoweb/settings.py` and adjust all the settings. Make sure that Redis
host/port are configured properly, configure database.
5. Run `manage.py makemigrations`.
6. Run `manage.py migrate`.
7. Populate `static/` directory: `manage.py collectstatic`.
8. Install the systemd service: `cp contrib/systemd/algoweb-poller.service /lib/systemd/system/`.
9. Enable poller service auto start: `systemctl enable algoweb-poller`.
10. Start poller service: `service algoweb-poller start`.
11. Configure the application on your apache2 (or another server) and start it:
https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/modwsgi/

## Fast route (development mode) ##
In order to get algoweb working even quicker, you need to:
* Perform points 1-6 from the above list.
* Execute `manage.py runpoller` - this is essential background task which should run continuously.
* Execute `manage.py runserver` - this is the proper HTTP development server.

## How to login ##
User authentication could be handled either by the external CAS server, internal Algochecker account mechanism (most natural) or both of them simultaneously.

The easiest way to play around without actually doing much configuration is to execute:
`manage.py createsuperuser`, create some account for yourself and then log in using internal account mechanism.
