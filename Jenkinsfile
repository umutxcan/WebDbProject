pipeline {
  agent any

  environment {
    IMAGE_NAME = "harbor.vmind.net/myproject/myapp:latest"
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
        sh '''
        docker run --rm \
          -v $(pwd):/workspace \
          -v /kaniko/.docker:/kaniko/.docker \
          -e DOCKER_CONFIG=/kaniko/.docker \
          gcr.io/kaniko-project/executor:latest \
          --dockerfile=/workspace/Dockerfile \
          --context=dir:///workspace \
          --destination=$IMAGE_NAME \
          --skip-tls-verify
        '''
      }
    }

    stage('Deploy to Swarm') {
      steps {
        sh '''
        docker service update --image $IMAGE_NAME myapp || \
        docker service create --name myapp --replicas 3 -p 80:5000 $IMAGE_NAME
        '''
      }
    }
  }
}
