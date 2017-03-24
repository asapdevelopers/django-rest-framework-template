# Django Rest Framework Template

## Requirements
    Python 2.7
    pip

## Features
* An API with login, change password and recovery password endpoints
* Django Rest Framework tests for those endpoints
* Error logs handlers for API errors
* An admin site (including error reports)
* API Throttling
* Email helper to send emails in both sync or async ways
* Amazon S3 integration using boto3 and Django files
* Code checker usign flake8
* Several tweaks to improve the performance
	
## Installation
    pip install -r requirements.txt
    Modify settings.py and wsgi.py to change various settings, private keys, access keys, and project/app names. Make sure to find and replace all names
    delete db.sqlite3
    ptyhon manage.py migrate
    python manage.py createsuperuser

## Run the server
    python manage.py runserver 0.0.0.0:8080

## Site URLs

Admin site: `http://localhost:8080/`
API: `http://localhost:8080/api/`
API docs: `http://localhost:8080/api/docs/`

## Tests
    python manage.py test clients.tests -k
    
## Check code
Flake8 is a static syntax and style checker for Python/Django source code
The command to run a code check is

    flake8 .