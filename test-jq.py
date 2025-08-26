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
        # 필요한 패키지 설치
        apt-get update && apt-get install -y curl unzip
        
        # Vault CLI 설치
        curl -fsSL https://releases.hashicorp.com/vault/1.20.2/vault_1.20.2_linux_amd64.zip -o vault.zip
        unzip vault.zip
        chmod +x vault
        mv vault /usr/local/bin/
        
        echo "Using Vault: $VAULT_ADDR"
        echo "Airflow Role ID: ${AIRFLOW_ROLE_ID:0:10}..."
        
        # Vault 환경변수 설정
        export VAULT_ADDR=$VAULT_ADDR
        
        # AIRFLOW로 Vault 로그인
        export VAULT_TOKEN=$(vault write -field=token auth/approle/login \
            role_id="$AIRFLOW_ROLE_ID" \
            secret_id="$AIRFLOW_SECRET_ID")
        
        # App role credentials 획득
        export VAULT_ROLE_ID=$(vault read -field=role_id auth/approle/role/app-role/role-id)
        export VAULT_SECRET_ID=$(vault write -field=secret_id auth/approle/role/app-role/secret-id)
        
        echo "Successfully obtained app-role credentials"
        echo "App Role ID: ${VAULT_ROLE_ID:0:10}..."
        echo "App Secret ID: ${VAULT_SECRET_ID:0:10}..."
        
        # JAR 실행
        curl -L -o app.jar https://github.com/scvit/terraform-aws-vpc_module/releases/download/1.0.3/udf-pki-1.0.0.jar
        java -jar app.jar
    '''],
    env_vars=[
        # 모든 값을 Airflow Variable에서 가져오기
        k8s.V1EnvVar(name='VAULT_ADDR', value='{{ var.value.vault_addr }}'),
        k8s.V1EnvVar(name='AIRFLOW_ROLE_ID', value='{{ var.value.airflow_role_id }}'),
        k8s.V1EnvVar(name='AIRFLOW_SECRET_ID', value='{{ var.value.airflow_secret_id }}'),
        k8s.V1EnvVar(name='KEY_NAME', value='key50')
    ],
    is_delete_operator_pod=False,
    dag=dag
)
