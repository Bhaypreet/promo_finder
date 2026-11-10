# Hugging Face Spaces (Docker SDK) or any container host. Set GROQ_API_KEY as a secret.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY promo_finder/ promo_finder/
COPY kb/ kb/
COPY run.py app.py ./
RUN useradd -m appuser && mkdir -p .cache && chown -R appuser /app
USER appuser
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
