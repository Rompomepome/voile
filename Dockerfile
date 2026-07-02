FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py tokenizer.py surfaces.py audit.py main.py ./
COPY recognizers/ ./recognizers/

EXPOSE 8080

# Les logs d'accès Uvicorn ne contiennent que méthode/chemin/statut, jamais
# les corps de requête ; on les coupe quand même par défense en profondeur.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]
