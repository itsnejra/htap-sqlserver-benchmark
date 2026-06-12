FROM python:3.11-slim

# Zrcali strukturu repozitorija: /app/Analysis/ i /app/Results/
# Analysis skripte koriste ANALYSIS_DIR.parent / "Results" za putanje
WORKDIR /app

COPY requirements.txt /app/Analysis/requirements.txt
RUN pip install --no-cache-dir -r /app/Analysis/requirements.txt

COPY . /app/Analysis/

# Results (ulaz iz benchmarka) i Figures (izlaz grafova) su mount pointovi
RUN mkdir -p /app/Results /app/Results/figures

ENTRYPOINT ["python", "/app/Analysis/run_all.py", "--skip-delete-bench"]
