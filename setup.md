# Create the environment

python3 -m venv venv

# Activate it

source venv/bin/activate

pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate

python manage.py seed_db

python manage.py runserver
