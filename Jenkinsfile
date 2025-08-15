pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds(); timeout(time: 30, unit: 'MINUTES') }

  parameters {
    string(name: 'REGISTRY',        defaultValue: 'harbor.umutcan.info', description: 'Harbor registry')
    string(name: 'PROJECT',         defaultValue: 'myproject',           description: 'Harbor project')
    string(name: 'IMAGE_NAME',      defaultValue: 'myapp',               description: 'Image name')
    string(name: 'IMAGE_TAG',       defaultValue: 'latest',              description: 'Image tag')
    string(name: 'DOCKERFILE_PATH', defaultValue: 'Dockerfile.dtb',      description: 'Dockerfile path')
  }

  environment {
    KANIKO_IMG = 'gcr.io/kaniko-project/executor:latest'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        sh 'git rev-parse --short HEAD | xargs echo "Git rev:"'
      }
    }

    stage('Preflight: Dockerfile check') {
      steps {
        sh '''#!/usr/bin/env sh
set -eu
echo ">> Using DOCKERFILE_PATH=${DOCKERFILE_PATH}"
[ -f "${DOCKERFILE_PATH}" ] || { echo "❌ ${DOCKERFILE_PATH} bulunamadı"; exit 1; }
echo "✅ Dockerfile OK -> ${DOCKERFILE_PATH}"
'''
      }
    }

    stage('Check Harbor Credentials') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'harbor-creds', usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
          sh 'echo "Harbor user OK: $REG_USER"'
        }
      }
    }

    stage('Build & Push (Kaniko)') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'harbor-creds', usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
          sh '''#!/usr/bin/env sh
set -eu

echo ">> Prepare Harbor auth for Kaniko"
mkdir -p "$HOME/.docker"
AUTH_B64=$(printf "%s" "${REG_USER}:${REG_PASS}" | base64 | tr -d '\\n')
cat > "$HOME/.docker/config.json" <<EOF
{"auths":{"https://${REGISTRY}":{"auth":"${AUTH_B64}"}}}
EOF

# Proxy env'lerini sadece tanımlıysa geçir
PROXY_ARGS=""
[ -n "${HTTP_PROXY:-}" ]  && PROXY_ARGS="$PROXY_ARGS -e HTTP_PROXY=$HTTP_PROXY"
[ -n "${HTTPS_PROXY:-}" ] && PROXY_ARGS="$PROXY_ARGS -e HTTPS_PROXY=$HTTPS_PROXY"
[ -n "${NO_PROXY:-}" ]    && PROXY_ARGS="$PROXY_ARGS -e NO_PROXY=$NO_PROXY"
[ -n "${http_proxy:-}" ]  && PROXY_ARGS="$PROXY_ARGS -e http_proxy=$http_proxy"
[ -n "${https_proxy:-}" ] && PROXY_ARGS="$PROXY_ARGS -e https_proxy=$https_proxy"
[ -n "${no_proxy:-}" ]    && PROXY_ARGS="$PROXY_ARGS -e no_proxy=$no_proxy"

echo ">> Building with Kaniko: ${DOCKERFILE_PATH}"
docker run --rm \
  -v "$PWD":/workspace \
  -v "$HOME/.docker":/kaniko/.docker:ro \
  -v /etc/ssl/certs:/etc/ssl/certs:ro \
  $PROXY_ARGS \
  ${KANIKO_IMG} \
  --context=dir:///workspace \
  --dockerfile="${DOCKERFILE_PATH}" \
  --destination="${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
'''
        }
      }
    }
  }

  post {
    success { echo '✅ Done.' }
    failure { echo '❌ Pipeline failed.' }
  }
}
