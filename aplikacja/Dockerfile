FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt requirements-lock.txt ./
# exact library versions used for the tests and the manuscript analyses
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
