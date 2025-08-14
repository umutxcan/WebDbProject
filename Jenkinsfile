pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 30, unit: 'MINUTES')
  }

  parameters {
    // ---- Registry / Image ----
    string(name: 'REGISTRY',    defaultValue: 'harbor.umutcan.info', description: 'Harbor registry')
    string(name: 'PROJECT',     defaultValue: 'myproject',           description: 'Harbor project')
    string(name: 'IMAGE_NAME',  defaultValue: 'myapp',               description: 'Image name')
    string(name: 'IMAGE_TAG',   defaultValue: 'latest',              description: 'Image tag')

    // ---- Build ----
    string(name: 'DOCKERFILE_PATH', defaultValue: 'docker/Dockerfile.app', description: 'Dockerfile path')
    booleanParam(name: 'USE_BASE',  defaultValue: false, description: 'Base imaj (harbor.../python-base:3.11) kullan')

    // ---- (Opsiyonel) Sağlık kontrolü ----
    booleanParam(name: 'HEALTHCHECK', defaultValue: false, description: 'Build sonrası public IP üzerinden health check yap')
    string(name: 'PUBLIC_IP',    defaultValue: '43.229.92.195', description: 'LB/Public IP')
    string(name: 'HEALTH_PATH',  defaultValue: '/health',       description: 'Health path')
    string(name: 'KUBILAY_PATH', defaultValue: '/kubilay',      description: 'Kubilay path')
    string(name: 'PROTOCOLS',    defaultValue: 'https,http',    description: 'Denenecek protokoller (virgülle): https,http')
  }

  environment {
    CREDS_ID   = 'harbor-creds'                     // Jenkins "Username with password"
    KANIKO_IMG = 'gcr.io/kaniko-project/executor:latest'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        sh 'echo "Git rev: $(git rev-parse --short HEAD)"'
      }
    }

    stage('Build & Push (Kaniko)') {
      steps {
        withCredentials([usernamePassword(credentialsId: "${CREDS_ID}", usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
          sh '''
            set -e
            echo ">> Preparing Docker auth for Kaniko"
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

            echo ">> Building & pushing ${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
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

    stage('Health Check (public IP)') {
      when { expression { return params.HEALTHCHECK } }
      steps {
        script {
          sh '''
            set +e
            IFS=',' read -r -a PROTOS <<< "${PROTOCOLS}"
            OK=0
            for proto in "${PROTOS[@]}"; do
              echo ">> Trying: $proto://${PUBLIC_IP}${HEALTH_PATH}"
              if curl -skI "$proto://${PUBLIC_IP}${HEALTH_PATH}" | grep -q "200"; then
                echo "Health OK via $proto"
                OK=1
                break
              fi
            done

            if [ $OK -eq 0 ]; then
              echo "WARN: Health check failed on all protocols: ${PROTOCOLS}"
              exit 1
            fi

            echo ">> Kubilay endpoint quick check"
            for proto in "${PROTOS[@]}"; do
              echo ">> $proto://${PUBLIC_IP}${KUBILAY_PATH}"
              if curl -sk "$proto://${PUBLIC_IP}${KUBILAY_PATH}" | grep -qi "kubilay kaptanoglu"; then
                echo "Kubilay endpoint OK via $proto"
                exit 0
              fi
            done

            echo "WARN: Kubilay endpoint not matched; continuing."
            exit 0
          '''
        }
      }
    }
  }

  post {
    success { echo "✅ Build & push complete." }
    failure { echo "❌ Pipeline failed." }
  }
}
