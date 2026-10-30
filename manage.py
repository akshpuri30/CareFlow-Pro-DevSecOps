import os
import sys
from getpass import getpass
from werkzeug.security import generate_password_hash
from app import app, db, User

if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] != 'create-admin':
        sys.exit('Usage: python manage.py create-admin')
    username = input('Admin username: ').strip()
    password = getpass('Admin password (12+ characters): ')
    if not username or len(password) < 12:
        sys.exit('Username required and password must be at least 12 characters.')
    with app.app_context():
        if db.session.scalar(db.select(User).filter_by(username=username)):
            sys.exit('Username already exists.')
        db.session.add(User(username=username, password_hash=generate_password_hash(password), role='admin'))
        db.session.commit()
    print('Admin created.')
