pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds(); timeout(time: 30, unit: 'MINUTES') }

  parameters {
    string(name: 'REGISTRY',        defaultValue: 'harbor.umutcan.info', description: 'Harbor registry')
    string(name: 'PROJECT',         defaultValue: 'myproject',           description: 'Harbor project')
    string(name: 'IMAGE_NAME',      defaultValue: 'myapp',               description: 'Image name')
    string(name: 'IMAGE_TAG',       defaultValue: 'latest',              description: 'Image tag')
    string(name: 'DOCKERFILE_PATH', defaultValue: 'Dockerfile.dtb',      description: 'Path to Dockerfile (örn: Dockerfile.dtb)')
    booleanParam(name: 'USE_BASE',  defaultValue: false,                 description: 'BASE_IMAGE=harbor.../python-base:3.11 kullan')
    string(name: 'CREDS_ID',        defaultValue: 'harbor-creds',        description: 'Harbor credentials ID (Username+Password)')
    // Cache
    string(name: 'CACHE_REPO',      defaultValue: 'harbor.umutcan.info/myproject/kaniko-cache', description: 'Kaniko cache repository')
    // Opsiyonel proxy (boş bırakabilirsin)
    string(name: 'HTTP_PROXY',      defaultValue: '', description: 'http_proxy (opsiyonel)')
    string(name: 'HTTPS_PROXY',     defaultValue: '', description: 'https_proxy (opsiyonel)')
    string(name: 'NO_PROXY',        defaultValue: '', description: 'no_proxy (opsiyonel)')
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

    stage('Preflight: Dockerfile check') {
      steps {
        withEnv(["DOCKERFILE_PATH=${params.DOCKERFILE_PATH}"]) {
          sh '''
            set -eu
            echo ">> Using DOCKERFILE_PATH=${DOCKERFILE_PATH}"
            [ -z "${DOCKERFILE_PATH}" ] && { echo "❌ DOCKERFILE_PATH parametresi boş"; exit 2; }
            [ -f "${DOCKERFILE_PATH}" ] || { echo "❌ Dockerfile yok: ${DOCKERFILE_PATH}"; ls -la || true; exit 2; }
            echo "✅ Dockerfile OK -> ${DOCKERFILE_PATH}"
          '''
        }
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
        withEnv([
          "DOCKERFILE_PATH=${params.DOCKERFILE_PATH}",
          "HTTP_PROXY=${params.HTTP_PROXY}",
          "HTTPS_PROXY=${params.HTTPS_PROXY}",
          "NO_PROXY=${params.NO_PROXY}"
        ]) {
          withCredentials([usernamePassword(credentialsId: "${params.CREDS_ID}", usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
            sh '''
              set -eu
              echo ">> Prepare Harbor auth for Kaniko"
              mkdir -p "$HOME/.docker"
              AUTH=$( (echo -n "${REG_USER}:${REG_PASS}" | base64 -w 0) 2>/dev/null || echo -n "${REG_USER}:${REG_PASS}" | base64 | tr -d '\n' )
              printf '{"auths":{"%s":{"auth":"%s"}}}\n' "${REGISTRY}" "${AUTH}" > "$HOME/.docker/config.json"

              # İsteğe bağlı base arg
              if [ "${USE_BASE}" = "true" ]; then
                BASE_ARG="--build-arg BASE_IMAGE=${REGISTRY}/${PROJECT}/python-base:3.11"
              else
                BASE_ARG=""
              fi

              # Opsiyonel proxy env’lerini Kaniko container’ına geçir
              PROXY_ENVS=""
              [ -n "${HTTP_PROXY}" ]  && PROXY_ENVS="${PROXY_ENVS} -e http_proxy=${HTTP_PROXY} -e HTTP_PROXY=${HTTP_PROXY}"
              [ -n "${HTTPS_PROXY}" ] && PROXY_ENVS="${PROXY_ENVS} -e https_proxy=${HTTPS_PROXY} -e HTTPS_PROXY=${HTTPS_PROXY}"
              [ -n "${NO_PROXY}" ]    && PROXY_ENVS="${PROXY_ENVS} -e no_proxy=${NO_PROXY} -e NO_PROXY=${NO_PROXY}"

              echo ">> Build & push ${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG} with ${DOCKERFILE_PATH}"
              # Cache açık; single-snapshot yok (layer’lar cache’lensin)
              docker run --rm \
                -v "$(pwd)":/workspace \
                -v "$HOME/.docker":/kaniko/.docker \
                ${PROXY_ENVS} \
                ${KANIKO_IMG} \
                --context=/workspace \
                --dockerfile="${DOCKERFILE_PATH}" \
                ${BASE_ARG} \
                --destination=${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG} \
                --digest-file /workspace/.kaniko_digest.txt \
                --verbosity=info \
                --cache=true \
                --cache-repo=${CACHE_REPO} \
                --cache-ttl=168h

              echo ">> Kaniko digest (proof):"
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
            REPO="${IMAGE_NAME}"
            curl -sfk -u "${U}:${P}" \
              "https://${REGISTRY}/api/v2.0/projects/${PROJECT}/repositories/${REPO}/artifacts?with_tag=true" \
              | grep -E "\"name\":\"${IMAGE_TAG}\"" -q && echo "Tag found on Harbor." || { echo "Tag NOT found!"; exit 1; }
          '''
        }
      }
    }
  }

  post {
    success { echo '✅ Build & push complete.' }
    failure { echo '❌ Pipeline failed.' }
  }
}
