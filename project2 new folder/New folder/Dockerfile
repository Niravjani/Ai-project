FROM python:3.10

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["streamlit", "run", "dairy_temperature_app.py", "--server.port=8000", "--server.address=0.0.0.0"]
