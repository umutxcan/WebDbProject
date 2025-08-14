pipeline {
  agent any

  options {
    ansiColor('xterm')
    timestamps()
    disableConcurrentBuilds()
  }

  parameters {
    booleanParam(name: 'BUILD_BASE', defaultValue: false, description: 'Build & push base image (python-base:3.11)')
    string(name: 'HEALTHCHECK_URL', defaultValue: 'https://umutcan.info/users', description: 'Health check URL (örn: https://umutcan.info/users veya http://43.229.92.195/users)')
    string(name: 'HEALTHCHECK_ATTEMPTS', defaultValue: '5', description: 'Health check deneme sayısı')
  }

  environment {
    // ---- REGISTRY / PROJECT ----
    REGISTRY             = 'harbor.umutcan.info'
    PROJECT              = 'myproject'
    REGISTRY_CREDENTIALS = 'harbor-creds'          // Jenkins Credentials ID (username+password)

    // ---- BASE IMAGE (opsiyonel) ----
    BASE_IMAGE_NAME      = 'python-base'
    BASE_TAG             = '3.11'
    BASE_DOCKERFILE_PATH = 'docker/python-base.Dockerfile'

    // ---- APP IMAGE ----
    IMAGE_NAME           = 'myapp'
    APP_DOCKERFILE_PATH  = 'Dockerfile'
    CONTEXT_DIR          = '.'

    // ---- REMOTE SWARM ----
    SWARM_HOST           = 'ubuntu@192.168.100.105' // Manager kullanıcı@IP
    SWARM_SSH            = 'swarm-manager-ssh'      // Jenkins SSH Private Key credentialsId

    // ---- DB ENV ----
    DB_CREDS             = 'db-creds'               // Jenkins Credentials (username+password)
    DB_NAME              = 'mydatabase'             // POSTGRES_DB

    // ---- Service & Network names ----
    APP_SERVICE          = 'flaskapp'
    DB_SERVICE           = 'myapp-db'
    OVERLAY_NET          = 'my_overlay'
    PUBLISHED_PORT       = '8080'
    CONTAINER_PORT       = '5000'
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Prepare tags') {
      steps {
        script {
          def gitShort = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
          env.IMAGE_TAG        = gitShort
          env.APP_IMAGE_FULL   = "${env.REGISTRY}/${env.PROJECT}/${env.IMAGE_NAME}:${env.IMAGE_TAG}"
          env.APP_IMAGE_LATEST = "${env.REGISTRY}/${env.PROJECT}/${env.IMAGE_NAME}:latest"
          env.BASE_IMAGE_FULL  = "${env.REGISTRY}/${env.PROJECT}/${env.BASE_IMAGE_NAME}:${env.BASE_TAG}"
          echo ">> APP_IMAGE:  ${env.APP_IMAGE_FULL}"
          echo ">> BASE_IMAGE: ${env.BASE_IMAGE_FULL}"
        }
      }
    }

    stage('Build & Push Base (Kaniko)') {
      when { expression { return params.BUILD_BASE } }
      steps {
        withCredentials([usernamePassword(credentialsId: env.REGISTRY_CREDENTIALS,
                                          usernameVariable: 'HARBOR_USER',
                                          passwordVariable: 'HARBOR_PASS')]) {
          sh """
            set -euo pipefail
            mkdir -p .docker
            AUTH=\$(printf "%s" "\$HARBOR_USER:\$HARBOR_PASS" | base64)
            cat > .docker/config.json <<'JSON'
            { "auths": { "${REGISTRY}": { "auth": "__AUTH__" } } }
            JSON
            sed -i "s/__AUTH__/\$AUTH/" .docker/config.json

            test -f "${BASE_DOCKERFILE_PATH}"

            docker run --rm \
              -v "\$PWD/${CONTEXT_DIR}":/workspace \
              -v "\$PWD/.docker":/kaniko/.docker \
              gcr.io/kaniko-project/executor:latest \
              --context=/workspace \
              --dockerfile=/workspace/${BASE_DOCKERFILE_PATH} \
              --destination="${BASE_IMAGE_FULL}" \
              --snapshotMode=redo --reproducible --single-snapshot
          """
        }
      }
    }

    stage('Build & Push App (Kaniko)') {
      steps {
        withCredentials([usernamePassword(credentialsId: env.REGISTRY_CREDENTIALS,
                                          usernameVariable: 'HARBOR_USER',
                                          passwordVariable: 'HARBOR_PASS')]) {
          sh """
            set -euo pipefail
            mkdir -p .docker
            AUTH=\$(printf "%s" "\$HARBOR_USER:\$HARBOR_PASS" | base64)
            cat > .docker/config.json <<'JSON'
            { "auths": { "${REGISTRY}": { "auth": "__AUTH__" } } }
            JSON
            sed -i "s/__AUTH__/\$AUTH/" .docker/config.json

            test -f "${APP_DOCKERFILE_PATH}"

            # Öneri: App Dockerfile'ında taban:
            # FROM ${REGISTRY}/${PROJECT}/${BASE_IMAGE_NAME}:${BASE_TAG}
            docker run --rm \
              -v "\$PWD/${CONTEXT_DIR}":/workspace \
              -v "\$PWD/.docker":/kaniko/.docker \
              gcr.io/kaniko-project/executor:latest \
              --context=/workspace \
              --dockerfile=/workspace/${APP_DOCKERFILE_PATH} \
              --destination="${APP_IMAGE_FULL}" \
              --destination="${APP_IMAGE_LATEST}" \
              --snapshotMode=redo --reproducible --single-snapshot
          """
        }
      }
    }

    stage('Deploy (service update/create)') {
      steps {
        withCredentials([
          sshUserPrivateKey(credentialsId: env.SWARM_SSH, keyFileVariable: 'SSH_KEY'),
          usernamePassword(credentialsId: env.DB_CREDS, usernameVariable: 'DB_USER', passwordVariable: 'DB_PASS'),
          usernamePassword(credentialsId: env.REGISTRY_CREDENTIALS, usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PASS')
        ]) {
          sh """
            set -euo pipefail

            # Değişkenleri remote shell ortamına enjekte ederek çalıştır
            ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" ${SWARM_HOST} \
              IMAGE='${APP_IMAGE_FULL}' \
              HARBOR_HOST='${REGISTRY}' \
              HARBOR_USER="$HARBOR_USER" \
              HARBOR_PASS="$HARBOR_PASS" \
              POSTGRES_USER="$DB_USER" \
              POSTGRES_PASSWORD="$DB_PASS" \
              POSTGRES_DB='${DB_NAME}' \
              APP_SERVICE='${APP_SERVICE}' \
              DB_SERVICE='${DB_SERVICE}' \
              OVERLAY_NET='${OVERLAY_NET}' \
              PUB_PORT='${PUBLISHED_PORT}' \
              CNT_PORT='${CONTAINER_PORT}' \
              bash -lc '
                set -euo pipefail

                echo "[login] harbor: \$HARBOR_HOST"
                docker login "\$HARBOR_HOST" -u "\$HARBOR_USER" -p "\$HARBOR_PASS" >/dev/null

                echo "[network] ensure overlay: \$OVERLAY_NET"
                docker network ls --format "{{.Name}}" | grep -x "\$OVERLAY_NET" || \
                  docker network create -d overlay --attachable "\$OVERLAY_NET"

                echo "[db] ensure service: \$DB_SERVICE"
                if ! docker service inspect "\$DB_SERVICE" >/dev/null 2>&1; then
                  docker service create \
                    --name "\$DB_SERVICE" \
                    --env POSTGRES_USER="\$POSTGRES_USER" \
                    --env POSTGRES_PASSWORD="\$POSTGRES_PASSWORD" \
                    --env POSTGRES_DB="\$POSTGRES_DB" \
                    --network "\$OVERLAY_NET" \
                    postgres:16
                fi

                if docker service inspect "\$APP_SERVICE" >/dev/null 2>&1; then
                  echo "[update] \$APP_SERVICE"
                  docker service update \
                    --env-rm POSTGRES_USER --env-rm POSTGRES_PASSWORD --env-rm POSTGRES_DB --env-rm DB_HOST --env-rm DB_PORT \
                    "\$APP_SERVICE" || true

                  docker service update \
                    --with-registry-auth \
                    --image "\$IMAGE" \
                    --env-add POSTGRES_USER="\$POSTGRES_USER" \
                    --env-add POSTGRES_PASSWORD="\$POSTGRES_PASSWORD" \
                    --env-add POSTGRES_DB="\$POSTGRES_DB" \
                    --env-add DB_HOST="\$DB_SERVICE" \
                    --env-add DB_PORT="5432" \
                    "\$APP_SERVICE"
                } else {
                  echo "[create] \$APP_SERVICE"
                  docker service create \
                    --name "\$APP_SERVICE" \
                    --replicas 3 \
                    --publish "\$PUB_PORT:\$CNT_PORT" \
                    --network "\$OVERLAY_NET" \
                    --with-registry-auth \
                    --env POSTGRES_USER="\$POSTGRES_USER" \
                    --env POSTGRES_PASSWORD="\$POSTGRES_PASSWORD" \
                    --env POSTGRES_DB="\$POSTGRES_DB" \
                    --env DB_HOST="\$DB_SERVICE" \
                    --env DB_PORT="5432" \
                    "\$IMAGE"
                }

                echo
                docker service ls
                echo
                docker service ps --no-trunc "\$APP_SERVICE"
              '
          """
        }
      }
    }

    stage('Health Check') {
      steps {
        script {
          // Build parametresinden gelir: örn. https://umutcan.info/users veya http://43.229.92.195/users
          def url = params.HEALTHCHECK_URL?.trim()
          def tries = params.HEALTHCHECK_ATTEMPTS?.trim()
          if (!url) { error("HEALTHCHECK_URL boş olamaz") }
          sh """
            set -e
            echo 'Health check → ${url}'
            i=0
            until [ \$i -ge ${tries} ]; do
              i=\$((i+1))
              code=\$(curl -s -k -o /dev/null -w "%{http_code}" "${url}")
              echo "Try \$i → HTTP \$code"
              [ "\$code" = "200" ] && exit 0
              sleep 3
            done
            echo "Health check failed"; exit 1
          """
        }
      }
    }
  }

  post {
    success { echo "✅ Deploy finished (services: ${env.APP_SERVICE}, ${env.DB_SERVICE})" }
    failure { echo "❌ Deployment FAILED" }
  }
}
