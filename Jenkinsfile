pipeline {
  agent any
  environment {
    IMAGE = 'careflow-pro:latest'
    MINIKUBE_HOME = '/var/lib/jenkins'
  }
  stages {
    stage('Checkout') { steps { checkout scm } }
    stage('Install and Test') {
      steps { sh '''
        python3 -m venv .venv
        .venv/bin/pip install -r requirements-dev.txt
        PYTHONPATH=. .venv/bin/python -m pytest -q
      ''' }
    }
    stage('Bandit SAST') {
      steps { sh '.venv/bin/bandit -r app.py manage.py -ll' }
    }
    stage('Dependency Audit') {
      steps { sh '.venv/bin/pip-audit -r requirements.txt' }
    }
    stage('Build Image') {
      steps { sh 'docker build -t "$IMAGE" .' }
    }
    stage('Trivy Image Scan') {
      steps { sh 'trivy image --exit-code 1 --severity HIGH,CRITICAL "$IMAGE"' }
    }
    stage('Deploy to Minikube') {
      steps { sh '''
        test -n "$MINIKUBE_HOME"
        kubectl get secret careflow-secrets >/dev/null
        minikube image load "$IMAGE"
        kubectl apply -f k8s/deployment.yaml
        kubectl rollout restart deployment/careflow-pro
        kubectl rollout status deployment/careflow-pro --timeout=180s
      ''' }
    }
    stage('Verify') { steps { sh 'kubectl get pods -l app=careflow-pro && kubectl get service careflow-pro' } }
  }
  post {
    success { echo 'CareFlow Pro DevSecOps pipeline completed successfully.' }
    failure { echo 'Pipeline blocked or failed. Inspect the failed security gate before deploying.' }
  }
}
