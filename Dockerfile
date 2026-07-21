FROM apify/actor-python:3.11

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m camoufox fetch

COPY . ./

CMD ["python", "-m", "src"]
