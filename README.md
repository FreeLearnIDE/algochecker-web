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
User registration and sign-in is not in the scope of Algochecker. Thus, it is required to setup a CAS-compatible
authentication server and then configure `CAS_*` properties in `algoweb/settings.py`.

If you want to play around without actually configuring valid CAS server, you can execute:
`manage.py createsuperuser`, create some account for yourself and navigate to: `http://localhost/admin/`.
After successful login re-navigate to the main page (`http://localhost/`) and you are done.
This workaround is suitable only for development purposes.
