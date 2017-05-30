#!/usr/bin/env python

import os
import crypt
from urllib.parse import quote
from flask import Flask, request, render_template, redirect, Response
from itsdangerous import URLSafeTimedSerializer, BadData
from hmac import compare_digest

from werkzeug.exceptions import Forbidden

app = Flask(__name__)

SECRET_KEY = 'd2uSaTheSAbrab7vaWewrAqaCuxEk5wU'
serializer = URLSafeTimedSerializer(SECRET_KEY)


def fetch_user(user_login):
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'accounts.txt'), 'r', encoding='utf8') as f:
        for line in f:
            if not line.strip():
                # empty line
                continue

            parts = line.strip().split(':')

            if parts[1] == user_login:
                return parts

    return None


@app.route("/")
def index():
    return Response('This is a Fake CAS server.', mimetype="text/plain")


@app.route("/serviceValidate", methods=['GET'])
def service_validate():
    ticket = request.args.get('ticket')
    service = request.args.get('service')

    try:
        data = serializer.loads(ticket, max_age=60)
    except BadData:
        raise Forbidden('Bad ticket')

    fetched_user = fetch_user(data)

    data = {
        "username": fetched_user[1],
        "employee_type": 'P' if fetched_user[0] == 'admin' else 'S',
        "first_name": fetched_user[2],
        "last_name": fetched_user[3]
    }

    print("Authenticated user: " + fetched_user[1])

    return Response(render_template('cas-success.xml', **data), mimetype="text/plain")


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    service = request.args.get('service')
    username = request.form.get('login')
    password = request.form.get('password')

    if not service:
        return render_template('login.html', error="Service address was not provided.")

    fetched_user = fetch_user(username)

    if not fetched_user:
        return render_template('login.html', error="Such user or password doesn\'t exist.")

    hashed = fetched_user[4]
    if not compare_digest(hashed, crypt.crypt(password, hashed)):
        return render_template('login.html', error="Such user or password doesn\'t exist.")

    ticket = serializer.dumps(fetched_user[1])

    if '?' in service:
        service += '&ticket=' + quote(ticket)
    else:
        service += '?ticket=' + quote(ticket)

    return redirect(service)


@app.route("/logout")
def logout():
    url = request.args.get('url')
    return redirect(url)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5044)
