pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds(); timeout(time: 30, unit: 'MINUTES') }

  parameters {
    string(name: 'IMAGE_TAG',       defaultValue: "latest",                description: 'Image tag (örn: latest ya da build-123)')
    string(name: 'DOCKERFILE_PATH', defaultValue: 'Dockerfile.dtb',        description: 'Dockerfile yolu (repo köküne göre)')
    booleanParam(name: 'USE_BASE',  defaultValue: true,                    description: 'BASE_IMAGE=harbor.../python-base:3.11 kullan')
    string(name: 'CACHE_REPO',      defaultValue: 'harbor.umutcan.info/myproject/kaniko-cache', description: 'Kaniko cache repo')
    string(name: 'CREDS_ID',        defaultValue: 'harbor-creds',          description: 'Harbor Jenkins Credentials (user+pass)')

    // ---- DB secret için iki seçenek: (1) düz param (geçici), (2) Jenkins Secret Text Credential ID
    string(name: 'DB_SECRET_PLAIN', defaultValue: '',                      description: 'Opsiyonel: Postgres şifresi (geçici ve test için). Boşsa kullanılmaz.')
    string(name: 'DB_SECRET_CRED_ID', defaultValue: 'pg-password',         description: 'Opsiyonel: Jenkins Secret Text ID (ör: pg-password)')
  }

  environment {
    REGISTRY   = 'harbor.umutcan.info'
    PROJECT    = 'myproject'
    IMAGE_NAME = 'myapp'

    // App runtime env
    DB_HOST = 'myapp-db'
    DB_USER = 'postgres'
    DB_NAME = 'postgres'
    SECRET_NAME   = 'pg_password'            // Swarm secret adı
    SECRET_TARGET = 'pg_password'            // Container içi target
    DB_PASS_FILE_PATH = '/run/secrets/pg_password'

    KANIKO_IMG = 'gcr.io/kaniko-project/executor:latest'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        sh 'echo "Git rev: $(git rev-parse --short HEAD)"'
      }
    }

    stage('Preflight: Dockerfile check') {
      steps {
        sh '''
          set -eu
          echo ">> Using DOCKERFILE_PATH=${DOCKERFILE_PATH}"
          [ -f "${DOCKERFILE_PATH}" ] || { echo "❌ Dockerfile yok: ${DOCKERFILE_PATH}"; ls -la || true; exit 2; }
          echo "✅ Dockerfile OK"
        '''
      }
    }

    stage('Docker Login (Harbor)') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${params.CREDS_ID}", usernameVariable: 'U', passwordVariable: 'P')]) {
          sh '''
            set -eu
            echo "$P" | docker login "${REGISTRY}" -u "$U" --password-stdin
          '''
        }
      }
    }

    stage('Build & Push (Kaniko + cache)') {
      steps {
        withEnv([
          "CACHE_REPO=${params.CACHE_REPO}",
          "USE_BASE=${params.USE_BASE}"
        ]) {
          withCredentials([usernamePassword(credentialsId: "${params.CREDS_ID}", usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
            sh '''
              set -eu
              echo ">> Prepare Harbor auth for Kaniko"
              mkdir -p "$HOME/.docker"
              AUTH=$( (echo -n "${REG_USER}:${REG_PASS}" | base64 -w 0) 2>/dev/null || echo -n "${REG_USER}:${REG_PASS}" | base64 | tr -d '\\n' )
              printf '{"auths":{"%s":{"auth":"%s"}}}\n' "${REGISTRY}" "${AUTH}" > "$HOME/.docker/config.json"

              if [ "${USE_BASE}" = "true" ]; then
                BASE_ARG="--build-arg BASE_IMAGE=${REGISTRY}/${PROJECT}/python-base:3.11"
              else
                BASE_ARG=""
              fi

              IMAGE_REF="${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
              echo ">> Build & push ${IMAGE_REF} with ${DOCKERFILE_PATH}"

              PROXY_ARGS=""
              [ -n "${HTTP_PROXY:-}" ]  && PROXY_ARGS="$PROXY_ARGS -e HTTP_PROXY=$HTTP_PROXY"
              [ -n "${HTTPS_PROXY:-}" ] && PROXY_ARGS="$PROXY_ARGS -e HTTPS_PROXY=$HTTPS_PROXY"
              [ -n "${NO_PROXY:-}" ]    && PROXY_ARGS="$PROXY_ARGS -e NO_PROXY=$NO_PROXY"
              [ -n "${http_proxy:-}" ]  && PROXY_ARGS="$PROXY_ARGS -e http_proxy=$http_proxy"
              [ -n "${https_proxy:-}" ] && PROXY_ARGS="$PROXY_ARGS -e https_proxy=$https_proxy"
              [ -n "${no_proxy:-}" ]    && PROXY_ARGS="$PROXY_ARGS -e no_proxy=$no_proxy"

              docker run --rm \
                -v "$(pwd)":/workspace \
                -v "$HOME/.docker":/kaniko/.docker \
                -v /etc/ssl/certs:/etc/ssl/certs:ro \
                $PROXY_ARGS \
                ${KANIKO_IMG} \
                --context=/workspace \
                --dockerfile="${DOCKERFILE_PATH}" \
                ${BASE_ARG} \
                --destination="${IMAGE_REF}" \
                --digest-file /workspace/.kaniko_digest.txt \
                --verbosity=info \
                --cache=true \
                --cache-repo="${CACHE_REPO}" \
                --cache-ttl=168h

              echo ">> Kaniko digest:"
              [ -s .kaniko_digest.txt ] && cat .kaniko_digest.txt || { echo "No digest file => push/build failed"; exit 1; }
            '''
          }
        }
      }
    }

    stage('Verify on Harbor') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${params.CREDS_ID}", usernameVariable: 'U', passwordVariable: 'P')]) {
          sh '''
            set -eu
            REPO_PATH="${PROJECT}/${IMAGE_NAME}"
            echo ">> Verifying tag via Harbor API (artifact by reference)"
            curl -sf -u "${U}:${P}" \
              "https://${REGISTRY}/api/v2.0/projects/${PROJECT}/repositories/${IMAGE_NAME}/artifacts/${IMAGE_TAG}" \
              > /dev/null && echo "✅ Tag ${IMAGE_TAG} exists on ${REGISTRY}/${REPO_PATH}" || { echo "❌ Tag ${IMAGE_TAG} NOT found on Harbor"; exit 1; }
          '''
        }
      }
    }

    stage('Ensure Swarm Secret') {
      steps {
        script {
          // 1) Secret zaten var mı?
          def exists = sh(returnStatus: true, script: "docker secret ls --format '{{.Name}}' | grep -w '^${env.SECRET_NAME}\$' >/dev/null") == 0
          if (exists) {
            echo "✅ Swarm secret already exists: ${env.SECRET_NAME}"
          } else {
            // 2) Parametre ile düz şifre verildiyse onu kullan (quoting sorunu yaşamamak için dosya yazıp pipe'lıyoruz)
            if (params.DB_SECRET_PLAIN?.trim()) {
              writeFile file: '.tmp_secret', text: params.DB_SECRET_PLAIN
              sh "docker secret create '${env.SECRET_NAME}' .tmp_secret >/dev/null"
              sh "shred -u .tmp_secret || rm -f .tmp_secret"
              echo "✅ Created secret from DB_SECRET_PLAIN: ${env.SECRET_NAME}"
            } else {
              // 3) Jenkins Secret Text credential dene; yoksa anlaşılır hata üret
              try {
                withCredentials([string(credentialsId: params.DB_SECRET_CRED_ID, variable: 'DB_SECRET')]) {
                  sh "printf '%s' \"\$DB_SECRET\" | docker secret create '${env.SECRET_NAME}' - >/dev/null"
                }
                echo "✅ Created secret from Jenkins credential '${params.DB_SECRET_CRED_ID}': ${env.SECRET_NAME}"
              } catch (e) {
                error "❌ Swarm secret yok ve oluşturulamadı: Lütfen ya 'DB_SECRET_PLAIN' parametresine şifre gir, ya da Jenkins'te Secret Text oluşturup ID'sini 'DB_SECRET_CRED_ID' olarak ver. (Mevcut: '${params.DB_SECRET_CRED_ID}')"
              }
            }
          }
        }
      }
    }

    stage('Deploy to Swarm') {
  steps {
    withCredentials([usernamePassword(credentialsId: "${params.CREDS_ID}", usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PASS')]) {
      sshagent(credentials: ['swarm-manager-ssh']) {
        sh """
          set -eu
          SSH_HOST=192.168.100.105
          SSH_USER=ubuntu

          SERVICE=flaskapp
          IMAGE_REF="${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
          SECRET_NAME="${SECRET_NAME}"
          SECRET_TARGET="${SECRET_TARGET}"
          DB_HOST="${DB_HOST}"
          DB_USER="${DB_USER}"
          DB_NAME="${DB_NAME}"
          DB_PASS_FILE_PATH="${DB_PASS_FILE_PATH}"

          ssh -o StrictHostKeyChecking=no \${SSH_USER}@\${SSH_HOST} '
            set -euo pipefail

            # Harbor login (kimlik bilgisini bu CLI üzerinden Swarm'a aktaralım)
            echo "${HARBOR_PASS}" | docker login "${REGISTRY}" -u "${HARBOR_USER}" --password-stdin

            # Network
            docker network inspect my_overlay >/dev/null 2>&1 || docker network create --driver overlay my_overlay

            if docker service ls --format "{{.Name}}" | grep -w "^${SERVICE}\$" >/dev/null; then
              # Secret bagli mi diye var
              if docker service inspect ${SERVICE} --format "{{json .Spec.TaskTemplate.ContainerSpec.Secrets}}" | grep -q "\"SecretName\":\"${SECRET_NAME}\""; then
                SECRET_ARGS="--secret-rm ${SECRET_TARGET} --secret-add source=${SECRET_NAME},target=${SECRET_TARGET}"
              else
                SECRET_ARGS="--secret-add source=${SECRET_NAME},target=${SECRET_TARGET}"
              fi

              docker service update \
                --with-registry-auth \
                --update-order stop-first \
                --update-parallelism 1 \
                --image ${IMAGE_REF} \
                --env-rm DB_PASS \
                --env-add DB_HOST=${DB_HOST} \
                --env-add DB_USER=${DB_USER} \
                --env-add DB_NAME=${DB_NAME} \
                --env-add DB_PASS_FILE=${DB_PASS_FILE_PATH} \
                ${SECRET_ARGS} \
                ${SERVICE}
            else
              docker service create --name ${SERVICE} --replicas 3 \
                --publish mode=ingress,target=5000,published=8080 \
                --network my_overlay \
                --with-registry-auth \
                --env DB_HOST=${DB_HOST} \
                --env DB_USER=${DB_USER} \
                --env DB_NAME=${DB_NAME} \
                --env DB_PASS_FILE=${DB_PASS_FILE_PATH} \
                --secret source=${SECRET_NAME},target=${SECRET_TARGET} \
                ${IMAGE_REF}
            fi
          '
        """
      }
    }
  }
}

  }

  post {
    always {
      sh '''
        set -e
        docker logout "${REGISTRY}" || true
      '''
      deleteDir()
    }
    success { echo '✅ Build, push ve deploy tamam.' }
    failure { echo '❌ Pipeline failed.' }
  }
}
