from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

dag = DAG(
    'vault_env',
    start_date=datetime(2024,1,1),
    schedule=None,
    catchup=False
)

task = BashOperator(
    task_id='vault_jar',
    bash_command="""
# Secret 읽기
JENKINS_ROLE_ID=$(cat /var/run/secrets/vault-credentials/vault-jenkins-role-id)
JENKINS_SECRET_ID=$(cat /var/run/secrets/vault-credentials/vault-jenkins-secret-id)

# Jenkins 토큰 획득
JENKINS_TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
    -d "{\\"role_id\\":\\"$JENKINS_ROLE_ID\\",\\"secret_id\\":\\"$JENKINS_SECRET_ID\\"}" \
    $VAULT_ADDR/v1/auth/approle/login | sed 's/.*"client_token":"\\([^"]*\\)".*/\\1/')

# App credentials 획득
VAULT_ROLE_ID=$(curl -s -H "X-Vault-Token: $JENKINS_TOKEN" \
    $VAULT_ADDR/v1/auth/approle/role/app-role/role-id | sed 's/.*"role_id":"\\([^"]*\\)".*/\\1/')

VAULT_SECRET_ID=$(curl -s -X POST -H "X-Vault-Token: $JENKINS_TOKEN" \
    $VAULT_ADDR/v1/auth/approle/role/app-role/secret-id | sed 's/.*"secret_id":"\\([^"]*\\)".*/\\1/')

export VAULT_ROLE_ID VAULT_SECRET_ID

echo "Vault credentials acquired"
echo "VAULT_ROLE_ID: $VAULT_ROLE_ID"

# JAR 다운로드
curl -L -o app.jar https://github.com/scvit/terraform-aws-vpc_module/releases/download/1.0.3/udf-pki-1.0.0.jar

# Java로 JAR 실행
java -jar app.jar
""",
    dag=dag
)
