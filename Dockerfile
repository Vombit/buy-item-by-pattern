FROM python:3.10-slim

WORKDIR /app

COPY . .
RUN pip install -r requirements.txt
RUN playwright install firefox 
RUN playwright install-deps firefox

CMD ["python", "-u", "main.py"]