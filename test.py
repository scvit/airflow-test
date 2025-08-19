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

# Java가 설치된 Pod에서 실행
task = KubernetesPodOperator(
    task_id='vault_jar',
    name='vault-jar-pod',
    namespace='airflow',
    image='openjdk:11-jre-slim',  # Java가 있는 이미지
    cmds=['/bin/bash'],
    arguments=['-c', '''
        # curl 설치
        apt-get update && apt-get install -y curl
        
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
        
        # JAR 다운로드 및 실행
        curl -L -o app.jar https://github.com/scvit/terraform-aws-vpc_module/releases/download/1.0.3/udf-pki-1.0.0.jar
        java -jar app.jar
    '''],
    env_vars=[
        k8s.V1EnvVar(name='VAULT_ADDR', value='http://4.230.150.183:8200')
    ],
    volumes=[
        k8s.V1Volume(
            name='vault-credentials',
            secret=k8s.V1SecretVolumeSource(secret_name='vault-credentials')
        )
    ],
    volume_mounts=[
        k8s.V1VolumeMount(
            name='vault-credentials',
            mount_path='/var/run/secrets/vault-credentials',
            read_only=True
        )
    ],
    is_delete_operator_pod=True,
    dag=dag
)
