FROM python:3.13-slim
WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy code
COPY . .

# run fastapi
EXPOSE 8000
CMD fastapi run --workers 4 src/main.py

