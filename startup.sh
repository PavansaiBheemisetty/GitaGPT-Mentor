cd backend

# Add this line 👇
export PYTHONPATH=$PYTHONPATH:/home/site/wwwroot/python_packages

uvicorn app.main:app --host 0.0.0.0 --port $PORT
