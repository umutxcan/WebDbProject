pipeline {
  agent any

  environment {
    IMAGE_NAME = "harbor.umutcan.info/myproject/myapp:latest"
    HARBOR_CREDS = credentials('harbor-credentials')  // Jenkins'te tanımlı
  }

  stages {
    stage('Checkout') {
      steps {
        git branch: 'master', url: 'https://github.com/umutxcan/WebDbProject.git'
      }
    }

    stage('Build Image with Kaniko') {
      steps {
        sh """
        docker run --rm --dns=8.8.8.8 \
          -v \$(pwd):/workspace \
          -v /kaniko/.docker:/kaniko/.docker \
          -e DOCKER_CONFIG=/kaniko/.docker \
          gcr.io/kaniko-project/executor:latest \
          --dockerfile=Dockerfile.dtb \
          --context=dir:///workspace \
          --destination=$IMAGE_NAME \
          --skip-tls-verify
        """
      }
    }

    stage('Deploy to Swarm') {
      steps {
        sh """
        ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no ubuntu@43.229.92.46 << 'ENDSSH'
          if docker service ls | grep -q myapp; then
            docker service update --image $IMAGE_NAME myapp
          else
            docker service create --name myapp --replicas 3 -p 5000:5000 $IMAGE_NAME
          fi
        ENDSSH
        """
      }
    }
  }
}

