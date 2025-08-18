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
# 환경 확인
echo "=== 환경 확인 ==="
whoami
echo "VAULT_ADDR: $VAULT_ADDR"

# Java 확인 (이미 설치되어 있는지)
if command -v java &> /dev/null; then
    echo "Java is available"
    java -version
else
    echo "Java is not available - checking alternatives"
    
    # 다른 Java 경로들 확인
    for java_path in /usr/bin/java /usr/lib/jvm/*/bin/java /opt/java/*/bin/java; do
        if [ -x "$java_path" ]; then
            echo "Found Java at: $java_path"
            export PATH="$(dirname $java_path):$PATH"
            break
        fi
    done
fi

# Secret에서 credentials 읽기  
echo "=== Secret 읽기 ==="
if [ -f "/var/run/secrets/vault-credentials/vault-jenkins-role-id" ]; then
    JENKINS_ROLE_ID=$(cat /var/run/secrets/vault-credentials/vault-jenkins-role-id)
    JENKINS_SECRET_ID=$(cat /var/run/secrets/vault-credentials/vault-jenkins-secret-id)
    echo "Secret 파일 읽기 성공"
    echo "Role ID 길이: ${#JENKINS_ROLE_ID}"
    echo "Secret ID 길이: ${#JENKINS_SECRET_ID}"
else
    echo "ERROR: Secret 파일이 없습니다"
    ls -la /var/run/secrets/ || echo "secrets 디렉토리 없음"
    exit 1
fi

# Vault 연결 테스트
echo "=== Vault 연결 테스트 ==="
vault_health=$(curl -s --connect-timeout 5 "$VAULT_ADDR/v1/sys/health" || echo "connection_failed")
if [[ "$vault_health" == "connection_failed" ]]; then
    echo "ERROR: Vault 서버에 연결할 수 없습니다"
    exit 1
fi
echo "Vault 연결 성공"

# Jenkins AppRole로 토큰 획득
echo "=== Jenkins AppRole 인증 ==="
auth_response=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "{\\"role_id\\":\\"$JENKINS_ROLE_ID\\",\\"secret_id\\":\\"$JENKINS_SECRET_ID\\"}" \
    "$VAULT_ADDR/v1/auth/approle/login")

echo "Auth response: $auth_response"

JENKINS_TOKEN=$(echo "$auth_response" | sed 's/.*"client_token":"\\([^"]*\\)".*/\\1/')

if [ -z "$JENKINS_TOKEN" ] || [ "$JENKINS_TOKEN" = "$auth_response" ]; then
    echo "ERROR: Jenkins 토큰 획득 실패"
    echo "Response: $auth_response"
    exit 1
fi

echo "Jenkins Token acquired successfully"

# App Role ID 획득
echo "=== App Role ID 획득 ==="
role_response=$(curl -s -H "X-Vault-Token: $JENKINS_TOKEN" \
    "$VAULT_ADDR/v1/auth/approle/role/app-role/role-id")

echo "Role response: $role_response"

VAULT_ROLE_ID=$(echo "$role_response" | sed 's/.*"role_id":"\\([^"]*\\)".*/\\1/')

if [ -z "$VAULT_ROLE_ID" ] || [ "$VAULT_ROLE_ID" = "$role_response" ]; then
    echo "ERROR: App Role ID 획득 실패"
    exit 1
fi

echo "App Role ID: $VAULT_ROLE_ID"

# App Secret ID 생성
echo "=== App Secret ID 생성 ==="
secret_response=$(curl -s -X POST -H "X-Vault-Token: $JENKINS_TOKEN" \
    "$VAULT_ADDR/v1/auth/approle/role/app-role/secret-id")

echo "Secret response: $secret_response"

VAULT_SECRET_ID=$(echo "$secret_response" | sed 's/.*"secret_id":"\\([^"]*\\)".*/\\1/')

if [ -z "$VAULT_SECRET_ID" ] || [ "$VAULT_SECRET_ID" = "$secret_response" ]; then
    echo "ERROR: App Secret ID 획득 실패"
    exit 1
fi

echo "App Secret ID acquired successfully"

# 환경 변수 설정
export VAULT_ROLE_ID="$VAULT_ROLE_ID"
export VAULT_SECRET_ID="$VAULT_SECRET_ID"

echo "=== 환경 변수 설정 완료 ==="
echo "VAULT_ADDR: $VAULT_ADDR"
echo "VAULT_ROLE_ID: $VAULT_ROLE_ID"
echo "VAULT_SECRET_ID: ${VAULT_SECRET_ID:0:10}..."

# JAR 다운로드
echo "=== JAR 파일 다운로드 ==="
curl -L --connect-timeout 10 --max-time 60 \
    -o udf-pki-1.0.0.jar \
    https://github.com/scvit/terraform-aws-vpc_module/releases/download/1.0.3/udf-pki-1.0.0.jar

if [ ! -f "udf-pki-1.0.0.jar" ]; then
    echo "ERROR: JAR 파일 다운로드 실패"
    exit 1
fi

echo "JAR 파일 다운로드 성공"

# JAR 실행 (Java가 있는 경우에만)
if command -v java &> /dev/null; then
    echo "=== JAR 실행 ==="
    java -jar udf-pki-1.0.0.jar
    echo "JAR 실행 완료"
else
    echo "=== Java 없이 완료 ==="
    echo "Java가 설치되어 있지 않아 JAR 실행은 건너뜁니다"
    echo "하지만 Vault 연동 및 환경 설정은 모두 성공했습니다"
fi

echo "=== 전체 작업 완료 ==="
''',
    dag=dag
)
