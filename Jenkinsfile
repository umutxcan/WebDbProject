pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds(); timeout(time: 30, unit: 'MINUTES') }

  parameters {
    string(name: 'IMAGE_TAG',       defaultValue: "latest",                description: 'Image tag (örn: latest ya da build-123)')
    string(name: 'DOCKERFILE_PATH', defaultValue: 'Dockerfile.dtb',        description: 'Dockerfile yolu (repo köküne göre)')
    booleanParam(name: 'USE_BASE',  defaultValue: true,                    description: 'BASE_IMAGE=harbor.../python-base:3.11 kullan')
    string(name: 'CACHE_REPO',      defaultValue: 'harbor.umutcan.info/myproject/kaniko-cache', description: 'Kaniko cache repo')
    string(name: 'CREDS_ID',        defaultValue: 'harbor-creds',          description: 'Harbor Jenkins Credentials (user+pass)')
  }

  environment {
    REGISTRY   = 'harbor.umutcan.info'
    PROJECT    = 'myproject'
    IMAGE_NAME = 'myapp'

    // Uygulama runtime env
    DB_HOST = 'myapp-db'
    DB_USER = 'postgres'
    DB_NAME = 'postgres'
    SECRET_NAME   = 'pg_password'
    SECRET_TARGET = 'pg_password'
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
        withEnv(["CACHE_REPO=${params.CACHE_REPO}"]) {
          withCredentials([usernamePassword(credentialsId: "${params.CREDS_ID}", usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
            sh '''
              set -eu
              echo ">> Prepare Harbor auth for Kaniko"
              mkdir -p "$HOME/.docker"
              AUTH=$( (echo -n "${REG_USER}:${REG_PASS}" | base64 -w 0) 2>/dev/null || echo -n "${REG_USER}:${REG_PASS}" | base64 | tr -d '\n' )
              printf '{"auths":{"%s":{"auth":"%s"}}}\n' "${REGISTRY}" "${AUTH}" > "$HOME/.docker/config.json"

              # İsteğe bağlı base arg (Dockerfile.dtb içinde ARG BASE_IMAGE olmalı)
              if [ "${USE_BASE}" = "true" ]; then
                BASE_ARG="--build-arg BASE_IMAGE=${REGISTRY}/${PROJECT}/python-base:3.11"
              else
                BASE_ARG=""
              fi

              IMAGE_REF="${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
              echo ">> Build & push ${IMAGE_REF} with ${DOCKERFILE_PATH}"

              docker run --rm \
                -v "$(pwd)":/workspace \
                -v "$HOME/.docker":/kaniko/.docker \
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
            echo ">> Checking tag via Harbor API"
            curl -sfk -u "${U}:${P}" \
              "https://${REGISTRY}/api/v2.0/projects/${PROJECT}/repositories/${IMAGE_NAME}/artifacts?with_tag=true" \
              | grep -E "\"name\":\"${IMAGE_TAG}\"" -q && echo "Tag found on Harbor." || { echo "Tag NOT found!"; exit 1; }
          '''
        }
      }
    }

    stage('Deploy to Swarm') {
      steps {
        sh '''
          set -eu
          docker network inspect app_net >/dev/null 2>&1 || docker network create --driver overlay app_net

          SERVICE=flaskapp
          IMAGE_REF="${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"

          if docker service ls --format '{{.Name}}' | grep -w "^${SERVICE}$" >/dev/null; then
            if docker service inspect "$SERVICE" --format '{{json .Spec.TaskTemplate.ContainerSpec.Secrets}}' | grep -q '"SecretName":"'"${SECRET_NAME}"'"'; then
              SECRET_ARGS="--secret-rm ${SECRET_TARGET} --secret-add source=${SECRET_NAME},target=${SECRET_TARGET}"
            else
              SECRET_ARGS="--secret-add source=${SECRET_NAME},target=${SECRET_TARGET}"
            fi

            docker service update \
              --with-registry-auth \
              --update-order stop-first \
              --update-parallelism 1 \
              --image "${IMAGE_REF}" \
              --publish-rm 8080 \
              --publish-add mode=host,target=8080,published=8080 \
              --env-rm DB_PASS \
              --env-add DB_HOST="${DB_HOST}" \
              --env-add DB_USER="${DB_USER}" \
              --env-add DB_NAME="${DB_NAME}" \
              --env-add DB_PASS_FILE="${DB_PASS_FILE_PATH}" \
              ${SECRET_ARGS} \
              "${SERVICE}"
          else
            docker service create --name "${SERVICE}" --replicas 3 \
              --publish mode=host,target=8080,published=8080 \
              --network app_net \
              --with-registry-auth \
              --env DB_HOST="${DB_HOST}" \
              --env DB_USER="${DB_USER}" \
              --env DB_NAME="${DB_NAME}" \
              --env DB_PASS_FILE="${DB_PASS_FILE_PATH}" \
              --secret source=${SECRET_NAME},target=${SECRET_TARGET} \
              "${IMAGE_REF}"
          fi
        '''
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
