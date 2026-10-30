# CareFlow Pro — Healthcare Management + DevSecOps

A full-stack **academic demonstration** with a responsive frontend, Flask backend, SQLAlchemy database, role-aware access, patient registry, doctor management, appointments, medical records, billing, audit log and DevSecOps pipeline.

**Use fictional patient data only. This is not a HIPAA-compliant or production-ready healthcare system.** The security center describes configured scans; it does not claim live results.

## Stack
- Frontend: Jinja HTML, responsive CSS, vanilla JavaScript
- Backend: Flask, Flask-Login, Flask-WTF CSRF, SQLAlchemy
- Database: SQLite for demo (PostgreSQL supported via `DATABASE_URL`)
- Operations: Gunicorn, Docker, Jenkins, Bandit, pip-audit, Trivy, Kubernetes (Minikube)

## Local setup (Python 3.11+)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
python manage.py create-admin
python app.py
```
Open `http://127.0.0.1:5000/login` and sign in with the admin you created. The SQLite DB is automatically created in the `instance` folder. Do **not** commit the DB or secrets.

## Tests and security

```bash
pytest -q
bandit -r app.py manage.py -ll
pip-audit -r requirements.txt
```

## Docker demo

```bash
cp .env.example .env
# edit .env and set a random SECRET_KEY
# docker compose exposes only 127.0.0.1:8086

docker compose up --build -d
# create admin in container (interactive)
docker compose exec web python manage.py create-admin
```

## GitHub → Jenkins → Minikube

1. Push this folder to a **private** GitHub repository. Keep `.env`, DB and patient data out of Git.
2. Install Jenkins prerequisites (Python venv, Docker access, kubectl, Minikube and Trivy). Grant only the permissions needed.
3. Start Minikube: `minikube start --driver=docker`.
4. Create a Kubernetes Secret **outside Git**:
   ```bash
   kubectl create secret generic careflow-secrets --from-literal=SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
   ```
5. Configure Jenkins as **Pipeline script from SCM** pointing to your repository's `Jenkinsfile`.
6. The pipeline runs tests, Bandit, pip-audit, Docker build, Trivy and then deploys to Minikube. Any failed security stage blocks deployment. **A passing pipeline is not guaranteed until dependencies and images have been reviewed and scans pass.**
7. First-time admin creation in Kubernetes:
   ```bash
   kubectl exec -it deployment/careflow-pro -- python manage.py create-admin
   ```
8. Access privately from EC2: `kubectl port-forward service/careflow-pro 8086:80` and use an SSH tunnel from your laptop if needed.

### Important Kubernetes demo limitations
SQLite is a single-writer database. This Kubernetes example uses **one replica** and a persistent volume, with `Recreate` rollout strategy to avoid simultaneous writers. For production, use managed PostgreSQL, migrations, backups, HTTPS ingress, network policies, rate limits, proper secret management, logging/monitoring, least privilege and security review. The `latest` tag is convenient for a lab but should be replaced with immutable build tags for real deployments. The default deployment assumes Minikube's image store and a storage class.

### Notes
- A new `SECRET_KEY` invalidates existing login sessions; keep it stable across restarts.
- HTTPS is needed before exposing any login over a public network; set `COOKIE_SECURE=1` behind HTTPS.
- Audit logs are basic app activity records, not tamper-proof audit trails.
- No real medical records, personal health information, or real payments should be stored.
- Security scans can flag issues that need remediation; do not bypass findings just to make a build green.
- Authentication roles: admin, doctor, receptionist (admin creation CLI included; additional user provisioning can be implemented later).
