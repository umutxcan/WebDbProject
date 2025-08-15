pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds(); timeout(time: 30, unit: 'MINUTES') }

  parameters {
    // ---- Harbor / Image ----
    string(name: 'REGISTRY',    defaultValue: 'harbor.umutcan.info', description: 'Harbor registry')
    string(name: 'PROJECT',     defaultValue: 'myproject',           description: 'Harbor project')
    string(name: 'IMAGE_NAME',  defaultValue: 'myapp',               description: 'Image name')
    string(name: 'IMAGE_TAG',   defaultValue: 'latest',              description: 'Image tag (örn. v1.0.1)')

    // ---- Build ----
    string(name: 'DOCKERFILE_PATH', defaultValue: 'Dockerfile.dtb', description: 'Dockerfile path')
    booleanParam(name: 'USE_BASE',  defaultValue: false, description: 'BASE_IMAGE=harbor.../python-base:3.11 kullan')
    string(name: 'CREDS_ID', defaultValue: 'harbor-creds', description: 'Harbor creds (Username+Password/robot)')
    booleanParam(name: 'SKIP_TLS_VERIFY_REG', defaultValue: false, description: 'Registry TLS verify skip (harbor self-signed vb.)')

    // ---- Network/Proxy ----
    string(name: 'HTTP_PROXY',  defaultValue: '', description: 'http proxy (opsiyonel)')
    string(name: 'HTTPS_PROXY', defaultValue: '', description: 'https proxy (opsiyonel)')
    string(name: 'NO_PROXY',    defaultValue: 'localhost,127.0.0.1,.local,harbor.umutcan.info,192.168.0.0/16,10.0.0.0/8', description: 'no_proxy listesi')

    // ---- Deploy (SSH ile Swarm manager) ----
    string(name: 'SERVICE_NAME', defaultValue: 'flaskapp', description: 'Swarm service adı (rolling update)')
    string(name: 'SSH_HOST',     defaultValue: 'ubuntu@192.168.100.105', description: 'Swarm manager SSH (kullanıcı@ip)')
    string(name: 'SSH_CRED_ID',  defaultValue: 'docker-node-ssh', description: 'Jenkins SSH key credentials ID')

    // ---- Health Check (LB/Public) ----
    booleanParam(name: 'HEALTHCHECK', defaultValue: true, description: 'Deploy sonrası public health check yap')
    string(name: 'PUBLIC_TARGET', defaultValue: '43.229.92.195', description: 'LB/Public IP veya domain')
    string(name: 'PUBLIC_HOST',   defaultValue: '', description: 'IP üzerinden test ederken Host header (örn: umutcan.info)')
    string(name: 'HEALTH_PATH',   defaultValue: '/health', description: 'Health path')
    string(name: 'KUBILAY_PATH',  defaultValue: '/kubilay', description: 'Kubilay path (opsiyonel)')
    string(name: 'PROTOCOLS',     defaultValue: 'http,https', description: 'Denenecek protokoller (virgülle)')
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
      environment {
        // Proxy env'lerini burada da export ediyoruz ki docker run -e ile Kaniko'ya geçsin
        HTTP_PROXY  = "${params.HTTP_PROXY}"
        HTTPS_PROXY = "${params.HTTPS_PROXY}"
        NO_PROXY    = "${params.NO_PROXY}"
      }
      steps {
        withCredentials([usernamePassword(credentialsId: "${params.CREDS_ID}", usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
          sh '''
            set -e
            echo ">> Prepare Harbor auth for Kaniko"
            mkdir -p "$HOME/.docker"
            AUTH="$(printf "%s:%s" "${REG_USER}" "${REG_PASS}" | base64 | tr -d '\\n')"
            printf '{"auths":{"https://%s":{"auth":"%s"}}}\n' "${REGISTRY}" "${AUTH}" > "$HOME/.docker/config.json"

            if [ "${USE_BASE}" = "true" ]; then
              BASE_ARG="--build-arg BASE_IMAGE=${REGISTRY}/${PROJECT}/python-base:3.11"
            else
              BASE_ARG=""
            fi

            EXTRA_REG=""
            if [ "${SKIP_TLS_VERIFY_REG}" = "true" ]; then
              EXTRA_REG="--skip-tls-verify-registry=${REGISTRY}"
            fi

            echo ">> Build & push ${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
            docker run --rm \
              -e HTTP_PROXY -e HTTPS_PROXY -e NO_PROXY \
              -v "$(pwd)":/workspace \
              -v "$HOME/.docker":/kaniko/.docker \
              ${KANIKO_IMG} \
              --context=/workspace \
              --dockerfile="${DOCKERFILE_PATH}" \
              ${BASE_ARG} \
              --destination="${REGISTRY}/${PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}" \
              --digest-file /workspace/.kaniko_digest.txt \
              --verbosity=info \
              --single-snapshot \
              ${EXTRA_REG}

            echo ">> Kaniko digest:"
            cat .kaniko_digest.txt || true
          '''
        }
      }
    }

    stage('Deploy to Swarm (rolling update via SSH)') {
      steps {
        script {
          env.IMAGE_FULL = "${params.REGISTRY}/${params.PROJECT}/${params.IMAGE_NAME}:${params.IMAGE_TAG}"
          echo "Deploying image: ${env.IMAGE_FULL} to service: ${params.SERVICE_NAME} @ ${params.SSH_HOST}"
        }
        sshagent (credentials: [ "${params.SSH_CRED_ID}" ]) {
          sh '''
            set -e
            ssh -o StrictHostKeyChecking=no ${SSH_HOST} "
              docker service update \
                --image ${IMAGE_FULL} \
                --update-order start-first \
                --update-parallelism 1 \
                --update-delay 10s \
                ${SERVICE_NAME} &&
              docker service ps --no-trunc ${SERVICE_NAME}
            "
          '''
        }
      }
    }

    stage('Public Health Check') {
      when { expression { return params.HEALTHCHECK } }
      steps {
        sh '''
          set +e
          OK=0
          # PROTOCOLS virgülleri boşluğa çevirerek POSIX uyumlu döngü
          for proto in $(echo "${PROTOCOLS}" | tr ',' ' '); do
            URL="${proto}://${PUBLIC_TARGET}${HEALTH_PATH}"
            echo ">> Checking: $URL"
            # Host header gerekiyorsa ekle
            if [ -n "${PUBLIC_HOST}" ]; then
              HDR="-H Host: ${PUBLIC_HOST}"
            else
              HDR=""
            fi

            # 5sn timeout, 2 retry, connrefused retry
            if curl -skI -m 5 --retry 2 --retry-delay 2 --retry-connrefused $HDR "$URL" | awk 'NR==1{print $2}' | grep -qE "^(200|204)$"; then
              echo "Health OK via $proto"
              OK=1
              break
            fi
          done

          if [ $OK -ne 1 ]; then
            echo "Health check FAILED on all protocols: ${PROTOCOLS}"
            exit 1
          fi

          # Kubilay (opsiyonel doğrulama)
          if [ -n "${KUBILAY_PATH}" ]; then
            for proto in $(echo "${PROTOCOLS}" | tr ',' ' '); do
              URL="${proto}://${PUBLIC_TARGET}${KUBILAY_PATH}"
              echo ">> Checking: $URL"
              if [ -n "${PUBLIC_HOST}" ]; then HDR="-H Host: ${PUBLIC_HOST}"; else HDR=""; fi
              if curl -sk -m 5 --retry 1 $HDR "$URL" | grep -qi "kubilay kaptanoglu"; then
                echo "Kubilay endpoint OK via $proto"
                exit 0
              fi
            done
            echo "WARN: Kubilay endpoint not matched (skipping failure)."
          fi
          exit 0
        '''
      }
    }
  }

  post {
    success { echo '✅ Build, push, deploy ve (varsa) health check tamam.' }
    failure { echo '❌ Pipeline failed.' }
  }
}
