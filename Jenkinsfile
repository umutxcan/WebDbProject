pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds() }

  parameters {
    string(name: 'HEALTHCHECK_URL', defaultValue: 'https://umutcan.info/users', description: 'örn: https://umutcan.info/users veya http://43.229.92.195/users')
  }

  environment {
    // ---- REGISTRY / IMAGE ----
    REGISTRY             = 'harbor.umutcan.info'
    PROJECT              = 'myproject'
    IMAGE_NAME           = 'myapp'
    REGISTRY_CREDENTIALS = 'harbor-creds'     // Jenkins Username+Password

    // ---- SWARM / DEPLOY ----
    SWARM_HOST           = 'ubuntu@192.168.100.105' // manager@ip
    SWARM_SSH            = 'swarm-manager-ssh'      // Jenkins SSH key
    APP_SERVICE          = 'flaskapp'
    PUBLISHED_PORT       = '8080'
    CONTAINER_PORT       = '5000'

    // ---- DB (servis zaten mevcut varsayımıyla) ----
    DB_CREDS             = 'db-creds'               // Username+Password
    DB_NAME              = 'mydatabase'
    DB_SERVICE           = 'myapp-db'               // Service DNS/hostname
  }

  stages {
    stage('Checkout') { steps { checkout scm } }

    stage('Tag & Image') {
      steps {
        script {
          env.IMAGE_TAG        = (env.GIT_COMMIT ?: sh(script:'git rev-parse --short HEAD', returnStdout:true).trim()).take(7)
          env.APP_IMAGE_FULL   = "${env.REGISTRY}/${env.PROJECT}/${env.IMAGE_NAME}:${env.IMAGE_TAG}"
          env.APP_IMAGE_LATEST = "${env.REGISTRY}/${env.PROJECT}/${env.IMAGE_NAME}:latest"
          echo "Image → ${env.APP_IMAGE_FULL}"
        }
      }
    }

    stage('Build & Push (Kaniko)') {
      steps {
        withCredentials([usernamePassword(credentialsId: env.REGISTRY_CREDENTIALS, usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PASS')]) {
          sh """
            set -e
            mkdir -p .docker
            AUTH=\$(printf "%s" "\$HARBOR_USER:\$HARBOR_PASS" | base64)
            cat > .docker/config.json <<EOF
            { "auths": { "${REGISTRY}": { "auth": "\$AUTH" } } }
            EOF

            docker run --rm \
              -v "\$PWD":/workspace \
              -v "\$PWD/.docker":/kaniko/.docker \
              gcr.io/kaniko-project/executor:latest \
              --context=/workspace \
              --dockerfile=/workspace/Dockerfile \
              --destination="${APP_IMAGE_FULL}" \
              --destination="${APP_IMAGE_LATEST}" \
              --snapshotMode=redo --reproducible --single-snapshot
          """
        }
      }
    }

    stage('Deploy') {
      steps {
        withCredentials([
          sshUserPrivateKey(credentialsId: env.SWARM_SSH, keyFileVariable: 'SSH_KEY'),
          usernamePassword(credentialsId: env.DB_CREDS, usernameVariable: 'DB_USER', passwordVariable: 'DB_PASS'),
          usernamePassword(credentialsId: env.REGISTRY_CREDENTIALS, usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PASS')
        ]) {
          sh """
            set -e
            ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" ${SWARM_HOST} \
              IMAGE='${APP_IMAGE_FULL}' \
              APP_SERVICE='${APP_SERVICE}' \
              DB_SERVICE='${DB_SERVICE}' \
              DB_NAME='${DB_NAME}' \
              DB_USER="$DB_USER" \
              DB_PASS="$DB_PASS" \
              PUBLISHED_PORT='${PUBLISHED_PORT}' \
              CONTAINER_PORT='${CONTAINER_PORT}' \
              REGISTRY='${REGISTRY}' \
              HARBOR_USER="$HARBOR_USER" \
              HARBOR_PASS="$HARBOR_PASS" \
              bash -lc '
                set -e
                docker login "$REGISTRY" -u "$HARBOR_USER" -p "$HARBOR_PASS" >/dev/null

                if docker service inspect "$APP_SERVICE" >/dev/null 2>&1; then
                  docker service update \
                    --with-registry-auth \
                    --image "$IMAGE" \
                    --env-add POSTGRES_USER="$DB_USER" \
                    --env-add POSTGRES_PASSWORD="$DB_PASS" \
                    --env-add POSTGRES_DB="$DB_NAME" \
                    --env-add DB_HOST="$DB_SERVICE" \
                    --env-add DB_PORT="5432" \
                    "$APP_SERVICE"
                else
                  docker service create \
                    --name "$APP_SERVICE" \
                    --replicas 3 \
                    --publish "$PUBLISHED_PORT:$CONTAINER_PORT" \
                    --with-registry-auth \
                    --env POSTGRES_USER="$DB_USER" \
                    --env POSTGRES_PASSWORD="$DB_PASS" \
                    --env POSTGRES_DB="$DB_NAME" \
                    --env DB_HOST="$DB_SERVICE" \
                    --env DB_PORT="5432" \
                    "$IMAGE"
                fi

                docker service ls | grep "$APP_SERVICE" || true
                docker service ps --no-trunc "$APP_SERVICE" || true
              '
          """
        }
      }
    }

    stage('Health Check') {
      steps {
        script {
          def url = params.HEALTHCHECK_URL?.trim()
          if (!url) { error('HEALTHCHECK_URL boş olamaz') }
          sh """
            set -e
            echo "Health → ${url}"
            for i in 1 2 3 4 5; do
              code=\$(curl -s -k -o /dev/null -w "%{http_code}" "${url}")
              echo "Try \$i: HTTP \$code"
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
    success { echo "✅ OK: ${env.APP_IMAGE_FULL}" }
    failure { echo "❌ FAILED" }
  }
}
