FROM python:3.13-slim
WORKDIR /app

# install dependencies
COPY requirements-all.txt .
RUN pip install --no-cache-dir -r requirements-all.txt

# copy code
COPY . .

# run tests
CMD poe test_e2e
