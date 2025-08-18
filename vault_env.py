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
    bash_command='''
# Secret에서 credentials 읽기  
JENKINS_ROLE_ID=$(cat /var/run/secrets/vault-credentials/vault-jenkins-role-id)
JENKINS_SECRET_ID=$(cat /var/run/secrets/vault-credentials/vault-jenkins-secret-id)

# Jenkins AppRole로 토큰 획득
JENKINS_TOKEN=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "{\\"role_id\\":\\"$JENKINS_ROLE_ID\\",\\"secret_id\\":\\"$JENKINS_SECRET_ID\\"}" \
    $VAULT_ADDR/v1/auth/approle/login | sed 's/.*"client_token":"\\([^"]*\\)".*/\\1/')

echo "Jenkins Token acquired"

# App Role ID 획득
ROLE_ID_RESPONSE=$(curl -s -H "X-Vault-Token: $JENKINS_TOKEN" \
    $VAULT_ADDR/v1/auth/approle/role/app-role/role-id)
export VAULT_ROLE_ID=$(echo $ROLE_ID_RESPONSE | sed 's/.*"role_id":"\\([^"]*\\)".*/\\1/')

# App Secret ID 생성
SECRET_ID_RESPONSE=$(curl -s -X POST -H "X-Vault-Token: $JENKINS_TOKEN" \
    $VAULT_ADDR/v1/auth/approle/role/app-role/secret-id)
export VAULT_SECRET_ID=$(echo $SECRET_ID_RESPONSE | sed 's/.*"secret_id":"\\([^"]*\\)".*/\\1/')

echo "App Role ID: $VAULT_ROLE_ID"
echo "App Secret ID acquired"

# JAR 실행
curl -L -o udf-pki-1.0.0.jar https://github.com/scvit/terraform-aws-vpc_module/releases/download/1.0.3/udf-pki-1.0.0.jar
java -jar udf-pki-1.0.0.jar
''',
    dag=dag,
    executor_config={
        "pod_override": {
            "spec": {
                "securityContext": {
                    "runAsUser": 0
                },
                "containers": [{
                    "name": "base",
                    "securityContext": {
                        "runAsUser": 0
                    },
                    "volumeMounts": [{
                        "name": "vault-credentials",
                        "mountPath": "/var/run/secrets/vault-credentials",
                        "readOnly": True
                    }]
                }],
                "volumes": [{
                    "name": "vault-credentials",
                    "secret": {
                        "secretName": "vault-credentials"
                    }
                }]
            }
        }
    }
)
