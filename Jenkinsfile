pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds(); timeout(time: 30, unit: 'MINUTES') }

  parameters {
    // ---- Harbor / Image ----
    string(name: 'REGISTRY',    defaultValue: 'harbor.umutcan.info', description: 'Harbor registry')
    string(name: 'PROJECT',     defaultValue: 'myproject',           description: 'Harbor project')
    string(name: 'IMAGE_NAME',  defaultValue: 'myapp',               description: 'App image name')
    string(name: 'IMAGE_TAG',   defaultValue: 'latest',              description: 'App image tag')

    // ---- Dockerfile yolları ----
    string(name: 'DOCKERFILE_PATH_APP',  defaultValue: 'Dockerfile.dtb',              description: 'Uygulama Dockerfile yolu')
    string(name: 'DOCKERFILE_PATH_BASE', defaultValue: 'docker/python-base.Dockerfile', description: 'Base image Dockerfile yolu')

    // ---- Base image opsiyonları ----
    booleanParam(name: 'BUILD_BASE', defaultValue: false, description: 'Önce base image build/push et')
    string(name: 'BASE_IMAGE_NAME',  defaultValue: 'python-base', description: 'Base image repo adı')
    string(name: 'BASE_TAG',         defaultValue: '3.11',        description: 'Base image tag (örn. 3.11)')

    // ---- Harbor credentials ----
    string(name: 'CREDS_ID', defaultValue: 'harbor-creds', description: 'Harbor credentials ID (Username+Password)')
  }

  environment {
    KANIKO_IMG = 'gcr.io/kaniko-project/executor:latest'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        sh 'echo "Git rev: $(git rev-parse --short HEAD)"'
      }
    }

    stage('Check Harbor Credentials') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${params.CREDS_ID}", usernameVariable: 'U', passwordVariable: 'P')]) {
          sh 'echo "Harbor user OK: ${U}"'
        }
      }
    }

    stage('Build & Push (Kaniko)') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${params.CREDS_ID}", usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
          sh '''
            set -euo pipefail
            echo ">> Prepare Harbor auth for Kaniko"
            mkdir -p "$HOME/.docker"
            AUTH="$(printf "%s:%s" "${REG_USER}" "${REG_PASS}" | base64 | tr -d '\\n')"
            printf '{"auths":{"https://%s":{"auth":"%s"}}}\n' "${REGISTRY}" "${AUTH}" > "$HOME/.docker/config.json"

            # Yollar var mı kontrol et
            [ -f "${DOCKERFILE_PATH_APP}" ]  || { echo "App Dockerfile not found: ${DOCKERFILE_PATH_APP}";   exit 1; }
            if [ "${BUILD_BASE}" = "true" ]; then
              [ -f "${DOCKERFILE_PATH_BASE}" ] || { echo "Base Dockerfile not found: ${DOCKERFILE_PATH_BASE}"; exit 1; }
            fi

            # (Opsiyonel) önce base image
            if [ "${BUILD_BASE}" = "true" ]; then
              echo ">> Build & push BASE: ${REGISTRY}/${PROJECT}/${BASE_IMAGE_NAME}:${BASE_TAG}"
              docker run --rm \
                -v "$(pwd)":/workspace \
                -v "$HOME/.docker":/kaniko/.docker \
                ${KANIKO_IMG} \
                --context=/workspace \
                --dockerfile="${DOCKERFILE_PATH_BASE}" \
                --destination="${REGISTRY}/${PROJECT}/${BASE_IMAGE_NAME}:${BASE_TAG}" \
                --digest-file /workspace/.kaniko_base_digest.txt \
                --verbosity=info --single-snapshot
              echo ">> Base digest:" && cat .kaniko_base_digest.txt || true
            fi

            # App build ARG: base image kullan
            if [ "${BUILD_BASE}" = "true" ]; then
              BASE_ARG="--build-arg BASE_IMAGE=${REGISTRY}/${PROJECT}/${BASE_IMAGE_NAME}:${BASE_TAG}"
            else
              BASE_ARG=""   # App Dockerfile kendi FROM satırını kullanır
            fi

            echo ">> Build & push APP: ${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
            docker run --rm \
              -v "$(pwd)":/workspace \
              -v "$HOME/.docker":/kaniko/.docker \
              ${KANIKO_IMG} \
              --context=/workspace \
              --dockerfile="${DOCKERFILE_PATH_APP}" \
              ${BASE_ARG} \
              --destination="${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}" \
              --digest-file /workspace/.kaniko_digest.txt \
              --verbosity=info --single-snapshot

            echo ">> App digest:" && cat .kaniko_digest.txt || { echo "No digest file => push/build failed"; exit 1; }
          '''
        }
      }
    }
  }

  post {
    success { echo '✅ Build & push tamam.' }
    failure { echo '❌ Pipeline failed.' }
  }
}
