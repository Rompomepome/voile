FROM python:3.11-slim

WORKDIR /app

# Modèle NER Tier 2 (~545 MB) : layer séparé, mis en cache indépendamment
# des changements de requirements.txt.
RUN pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/fr_core_news_lg-3.8.0/fr_core_news_lg-3.8.0-py3-none-any.whl

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py tokenizer.py surfaces.py audit.py main.py ./
COPY recognizers/ ./recognizers/

EXPOSE 8080

# Les logs d'accès Uvicorn ne contiennent que méthode/chemin/statut, jamais
# les corps de requête ; on les coupe quand même par défense en profondeur.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]
