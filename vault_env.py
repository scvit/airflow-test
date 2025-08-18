from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

dag = DAG(
    'vault_env',
    start_date=datetime(2024,1,1),
    schedule=None,  # schedule_interval → schedule
    catchup=False
)

task = BashOperator(
    task_id='vault_jar',
    bash_command='''

# 시스템 환경변수에서 jenkins credentials 가져오기
echo "Jenkins Role ID: $JENKINS_ROLE_ID"

# Jenkins AppRole로 토큰 획득
JENKINS_TOKEN=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "{\\"role_id\\":\\"$JENKINS_ROLE_ID\\",\\"secret_id\\":\\"$JENKINS_SECRET_ID\\"}" \
    $VAULT_ADDR/v1/auth/approle/login | \
    python3 -c "import sys, json; print(json.load(sys.stdin)['auth']['client_token'])")

# App credentials 획득
APP_ROLE_ID=$(curl -s -H "X-Vault-Token: $JENKINS_TOKEN" \
    $VAULT_ADDR/v1/auth/approle/role/app-role/role-id | \
    python3 -c "import sys, json; print(json.load(sys.stdin)['data']['role_id'])")

APP_SECRET_ID=$(curl -s -X POST -H "X-Vault-Token: $JENKINS_TOKEN" \
    $VAULT_ADDR/v1/auth/approle/role/app-role/secret-id | \
    python3 -c "import sys, json; print(json.load(sys.stdin)['data']['secret_id'])")

export VAULT_ROLE_ID="$APP_ROLE_ID"
export VAULT_SECRET_ID="$APP_SECRET_ID"

# JAR 실행
curl -L -o app.jar https://github.com/scvit/terraform-aws-vpc_module/releases/download/1.0.3/udf-pki-1.0.0.jar
java -jar app.jar
''',
    dag=dag
)
