pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds(); timeout(time: 30, unit: 'MINUTES') }

  parameters {
    string(name: 'REGISTRY',    defaultValue: 'harbor.umutcan.info', description: 'Harbor registry')
    string(name: 'PROJECT',     defaultValue: 'myproject',           description: 'Harbor project')
    string(name: 'IMAGE_NAME',  defaultValue: 'myapp',               description: 'Image name')
    string(name: 'IMAGE_TAG',   defaultValue: 'latest',              description: 'Image tag')
    string(name: 'DOCKERFILE_PATH', defaultValue: 'docker/Dockerfile.app', description: 'Dockerfile path')
    booleanParam(name: 'USE_BASE',  defaultValue: false, description: 'BASE_IMAGE=harbor.../python-base:3.11 kullan')
    string(name: 'CREDS_ID', defaultValue: 'harbor-creds', description: 'Harbor credentials ID (Username+Password)')
  }

  environment {
    KANIKO_IMG = 'gcr.io/kaniko-project/executor:latest'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm  // GitHub için job’da tanımlı githubCred zaten burada kullanılıyor
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
            set -e
            echo ">> Prepare auth for Kaniko"
            mkdir -p $HOME/.docker
            AUTH=$(echo -n "${REG_USER}:${REG_PASS}" | base64 -w 0)
            cat > $HOME/.docker/config.json <<EOF
            { "auths": { "https://${REGISTRY}": { "auth": "${AUTH}" } } }
            EOF

            if [ "${USE_BASE}" = "true" ]; then
              BASE_ARG="--build-arg BASE_IMAGE=${REGISTRY}/${PROJECT}/python-base:3.11"
            else
              BASE_ARG=""
            fi

            echo ">> Build & push ${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
            docker run --rm \
              -v $(pwd):/workspace \
              -v $HOME/.docker:/kaniko/.docker \
              ${KANIKO_IMG} \
              --context=/workspace \
              --dockerfile=${DOCKERFILE_PATH} \
              ${BASE_ARG} \
              --destination=${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG} \
              --single-snapshot
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