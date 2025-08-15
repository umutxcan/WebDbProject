pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds(); timeout(time: 30, unit: 'MINUTES') }

  parameters {
    string(name: 'REGISTRY',        defaultValue: 'harbor.umutcan.info', description: 'Harbor registry')
    string(name: 'PROJECT',         defaultValue: 'myproject',           description: 'Harbor project')
    string(name: 'IMAGE_NAME',      defaultValue: 'myapp',               description: 'Image name')
    string(name: 'IMAGE_TAG',       defaultValue: 'latest',              description: 'Image tag')
    // Sende mevcut olan ana Dockerfile: Dockerfile.dtb
    string(name: 'DOCKERFILE_PATH', defaultValue: 'docker/Dockerfile.dtb', description: 'Path to Dockerfile (örn: docker/Dockerfile.dtb)')
    booleanParam(name: 'USE_BASE',  defaultValue: false, description: 'BASE_IMAGE=harbor.../python-base:3.11 kullan')
    string(name: 'CREDS_ID',        defaultValue: 'harbor-creds',        description: 'Harbor credentials ID (Username+Password)')
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
        sh '''
          set -eu
          if [ ! -f "${DOCKERFILE_PATH}" ]; then
            echo "❌ Dockerfile bulunamadı: ${DOCKERFILE_PATH}"
            echo "Mevcut docker/ dizini içeriği:"
            ls -la docker || true
            exit 2
          fi
          echo "✅ Dockerfile OK -> ${DOCKERFILE_PATH}"
        '''
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
            set -eu
            echo ">> Prepare Harbor auth for Kaniko"
            mkdir -p "$HOME/.docker"
            # GNU base64 -w 0 yoksa alternatifle satır sonlarını kaldır
            AUTH=$( (echo -n "${REG_USER}:${REG_PASS}" | base64 -w 0) 2>/dev/null || echo -n "${REG_USER}:${REG_PASS}" | base64 | tr -d '\n' )

            # Kaniko için protokolsüz key daha uyumlu (https:// ekleme)
            printf '{"auths":{"%s":{"auth":"%s"}}}\n' "${REGISTRY}" "${AUTH}" > "$HOME/.docker/config.json"

            if [ "${USE_BASE}" = "true" ]; then
              BASE_ARG="--build-arg BASE_IMAGE=${REGISTRY}/${PROJECT}/python-base:3.11"
            else
              BASE_ARG=""
            fi

            echo ">> Build & push ${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
            docker run --rm \
              -v "$(pwd)":/workspace \
              -v "$HOME/.docker":/kaniko/.docker \
              ${KANIKO_IMG} \
              --context=/workspace \
              --dockerfile=${DOCKERFILE_PATH} \
              ${BASE_ARG} \
              --destination=${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG} \
              --digest-file /workspace/.kaniko_digest.txt \
              --verbosity=info \
              --single-snapshot

            echo ">> Kaniko digest (proof):"
            if [ -s .kaniko_digest.txt ]; then
              cat .kaniko_digest.txt
            else
              echo "No digest file => push/build failed"
              exit 1
            fi
          '''
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
