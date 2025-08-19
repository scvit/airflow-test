from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s
from datetime import datetime

dag = DAG(
    'vault_test',
    start_date=datetime(2024,1,1),
    schedule=None,
    catchup=False
)

task = KubernetesPodOperator(
    task_id='vault_jar',
    name='vault-jar-pod',
    namespace='airflow',
    image='openjdk:17-jdk-slim',
    cmds=['/bin/bash'],
    arguments=['-c', '''
        # curl 설치
        apt-get update && apt-get install -y curl
        
        echo "Using Vault: $VAULT_ADDR"
        echo "Jenkins Role ID: ${JENKINS_ROLE_ID:0:10}..."
        
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
        
        # JAR 실행
        curl -L -o app.jar https://github.com/scvit/terraform-aws-vpc_module/releases/download/1.0.3/udf-pki-1.0.0.jar
        java -jar app.jar
    '''],
    env_vars=[
        # 모든 값을 Airflow Variable에서 가져오기
        k8s.V1EnvVar(name='VAULT_ADDR', value='{{ var.value.vault_addr }}'),
        k8s.V1EnvVar(name='JENKINS_ROLE_ID', value='{{ var.value.jenkins_role_id }}'),
        k8s.V1EnvVar(name='JENKINS_SECRET_ID', value='{{ var.value.jenkins_secret_id }}'),
    ],
    is_delete_operator_pod=True,
    dag=dag
)
