# To run the backend
```bash
cd backend
python -m venv venv
venv/scripts/activate
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```
# To run the frontend
```bash
cd frontend
npm install 
npm run dev
```

