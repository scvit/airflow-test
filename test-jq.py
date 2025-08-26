from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s
from datetime import datetime

dag = DAG(
    'test-jq',
    start_date=datetime(2024,1,1),
    schedule=None,
    catchup=False
)

task = KubernetesPodOperator(
    task_id='test-jq',
    name='test-jq',
    namespace='airflow',
    image='openjdk:17-jdk-slim',
    cmds=['/bin/bash'],
    arguments=['-c', '''
        # curl 설치
        apt-get update && apt-get install -y curl jq
        
        echo "Using Vault: $VAULT_ADDR"
        echo "Airflow Role ID: ${AIRFLOW_ROLE_ID:0:10}..."
        
        # AIRFLOW 토큰 획득
        AIRFLOW_TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
    -d "{\"role_id\":\"$AIRFLOW_ROLE_ID\",\"secret_id\":\"$AIRFLOW_SECRET_ID\"}" \
    $VAULT_ADDR/v1/auth/approle/login | jq -r '.auth.client_token')
        
        # App credentials 획득
VAULT_ROLE_ID=$(curl -s -H "X-Vault-Token: $AIRFLOW_TOKEN" \
    $VAULT_ADDR/v1/auth/approle/role/app-role/role-id | jq -r '.data.role_id')

VAULT_SECRET_ID=$(curl -s -X POST -H "X-Vault-Token: $AIRFLOW_TOKEN" \
    $VAULT_ADDR/v1/auth/approle/role/app-role/secret-id | jq -r '.data.secret_id')

export VAULT_ROLE_ID VAULT_SECRET_ID
        
        # JAR 실행
        curl -L -o app.jar https://github.com/scvit/terraform-aws-vpc_module/releases/download/1.0.3/udf-pki-1.0.0.jar
        java -jar app.jar
    '''],
    env_vars=[
        # 모든 값을 Airflow Variable에서 가져오기
        k8s.V1EnvVar(name='VAULT_ADDR', value='{{ var.value.vault_addr }}'),
        k8s.V1EnvVar(name='AIRFLOW_ROLE_ID', value='{{ var.value.airflow_role_id }}'),
        k8s.V1EnvVar(name='AIRFLOW_SECRET_ID', value='{{ var.value.airflow_secret_id }}'),
        k8s.V1EnvVar(name='KEY_NAME', value='airflowkey')
    ],
    is_delete_operator_pod=False,
    dag=dag
)
