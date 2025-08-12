pipeline {
  agent any
  options {
    ansiColor('xterm')
    timestamps()
    disableConcurrentBuilds()
  }

  parameters {
    // İstersen taban imajı (python-base:3.11) da pipeline'da build etmek için true yap
    booleanParam(name: 'BUILD_BASE', defaultValue: false, description: 'Build & push base image (python-base:3.11)')
  }

  environment {
    // ---- REGISTRY / PROJECT ----
    REGISTRY             = 'harbor.umutcan.info'
    PROJECT              = 'myproject'
    REGISTRY_CREDENTIALS = 'harbor-creds'          // Jenkins Credentials ID (username+password)

    // ---- BASE IMAGE (opsiyonel) ----
    BASE_IMAGE_NAME      = 'python-base'
    BASE_TAG             = '3.11'
    BASE_DOCKERFILE_PATH = 'docker/python-base.Dockerfile' // sende: FROM python:3.11 + libpq-dev, gcc...

    // ---- APP IMAGE (senin servis adın "myapp") ----
    IMAGE_NAME           = 'myapp'
    APP_DOCKERFILE_PATH  = 'Dockerfile'            // sende: FROM harbor.../python-base:3.11
    CONTEXT_DIR          = '.'

    // ---- REMOTE SWARM ----
    SWARM_HOST           = 'ubuntu@192.168.100.105' // Manager kullanıcı@IP (kendine göre değiştir)
    SWARM_SSH            = 'swarm-manager-ssh'      // Jenkins SSH Private Key credentialsId

    // ---- DB ENV ----
    DB_CREDS             = 'db-creds'               // Jenkins Credentials (username+password)
    DB_NAME              = 'mydatabase'             // POSTGRES_DB (sende böyle)

    // ---- Service & Network names (sende bunlar) ----
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
          def short = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
          env.IMAGE_TAG      = short
          env.APP_IMAGE_FULL = "${env.REGISTRY}/${env.PROJECT}/${env.IMAGE_NAME}:${env.IMAGE_TAG}"
          env.APP_IMAGE_LTS  = "${env.REGISTRY}/${env.PROJECT}/${env.IMAGE_NAME}:latest"
          env.BASE_IMAGE_FULL= "${env.REGISTRY}/${env.PROJECT}/${env.BASE_IMAGE_NAME}:${env.BASE_TAG}"
          echo ">> APP_IMAGE: ${env.APP_IMAGE_FULL}"
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
            set -e
            mkdir -p .docker
            AUTH=\$(echo -n "\$HARBOR_USER:\$HARBOR_PASS" | base64)
            cat > .docker/config.json <<EOF
            { "auths": { "https://${env.REGISTRY}": { "auth": "\$AUTH" } } }
            EOF

            test -f "${env.BASE_DOCKERFILE_PATH}"

            docker run --rm \\
              -v "\$PWD/${env.CONTEXT_DIR}":/workspace \\
              -v "\$PWD/.docker":/kaniko/.docker \\
              gcr.io/kaniko-project/executor:latest \\
              --context=/workspace \\
              --dockerfile=/workspace/${env.BASE_DOCKERFILE_PATH} \\
              --destination="${env.BASE_IMAGE_FULL}" \\
              --force
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
            set -e
            mkdir -p .docker
            AUTH=\$(echo -n "\$HARBOR_USER:\$HARBOR_PASS" | base64)
            cat > .docker/config.json <<EOF
            { "auths": { "https://${env.REGISTRY}": { "auth": "\$AUTH" } } }
            EOF

            test -f "${env.APP_DOCKERFILE_PATH}"

            # App Dockerfile'ında taban: FROM ${env.REGISTRY}/${env.PROJECT}/${env.BASE_IMAGE_NAME}:${env.BASE_TAG}
            docker run --rm \\
              -v "\$PWD/${env.CONTEXT_DIR}":/workspace \\
              -v "\$PWD/.docker":/kaniko/.docker \\
              gcr.io/kaniko-project/executor:latest \\
              --context=/workspace \\
              --dockerfile=/workspace/${env.APP_DOCKERFILE_PATH} \\
              --destination="${env.APP_IMAGE_FULL}" \\
              --destination="${env.APP_IMAGE_LTS}" \\
              --force
          """
        }
      }
    }

    stage('Deploy (service update/create)') {
      steps {
        withCredentials([
          sshUserPrivateKey(credentialsId: env.SWARM_SSH, keyFileVariable: 'SSH_KEY'),
          usernamePassword(credentialsId: env.DB_CREDS, usernameVariable: 'DB_USER', passwordVariable: 'DB_PASS')
        ]) {
          sh """
            set -e
            # --- Remote script ---
            ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" ${env.SWARM_HOST} bash -lc '
              set -e

              IMAGE="${env.APP_IMAGE_FULL}"
              POSTGRES_USER="$DB_USER"
              POSTGRES_PASSWORD="$DB_PASS"
              POSTGRES_DB="${env.DB_NAME}"

              # 1) Ağ hazır mı?
              docker network ls --format "{{.Name}}" | grep -x ${env.OVERLAY_NET} || \\
                docker network create -d overlay ${env.OVERLAY_NET}

              # 2) DB servisi yoksa oluştur
              if ! docker service inspect ${env.DB_SERVICE} >/dev/null 2>&1; then
                echo "[create] ${env.DB_SERVICE}"
                docker service create \\
                  --name ${env.DB_SERVICE} \\
                  --env POSTGRES_USER="$POSTGRES_USER" \\
                  --env POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \\
                  --env POSTGRES_DB="$POSTGRES_DB" \\
                  --network ${env.OVERLAY_NET} \\
                  postgres:16
              else
                echo "[skip] ${env.DB_SERVICE} already exists"
              fi

              # 3) App servisi varsa update, yoksa create
              if docker service inspect ${env.APP_SERVICE} >/dev/null 2>&1; then
                echo "[update] ${env.APP_SERVICE}"
                # (Varsa eski ENV'leri temizlemeye çalış; yoksa hata vermesin)
                docker service update \\
                  --env-rm POSTGRES_USER --env-rm POSTGRES_PASSWORD --env-rm POSTGRES_DB --env-rm DB_HOST --env-rm DB_PORT \\
                  ${env.APP_SERVICE} || true

                docker service update \\
                  --with-registry-auth \\
                  --image "$IMAGE" \\
                  --env-add POSTGRES_USER="$POSTGRES_USER" \\
                  --env-add POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \\
                  --env-add POSTGRES_DB="$POSTGRES_DB" \\
                  --env-add DB_HOST="${env.DB_SERVICE}" \\
                  --env-add DB_PORT="5432" \\
                  ${env.APP_SERVICE}
              else
                echo "[create] ${env.APP_SERVICE}"
                docker service create \\
                  --name ${env.APP_SERVICE} \\
                  --replicas 3 \\
                  --publish ${env.PUBLISHED_PORT}:${env.CONTAINER_PORT} \\
                  --network ${env.OVERLAY_NET} \\
                  --with-registry-auth \\
                  --env POSTGRES_USER="$POSTGRES_USER" \\
                  --env POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \\
                  --env POSTGRES_DB="$POSTGRES_DB" \\
                  --env DB_HOST="${env.DB_SERVICE}" \\
                  --env DB_PORT="5432" \\
                  "$IMAGE"
              fi

              echo; docker service ls
              echo; docker service ps --no-trunc ${env.APP_SERVICE}
            '
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