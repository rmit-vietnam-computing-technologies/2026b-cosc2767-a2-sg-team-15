// RMIT University Vietnam
// Course: COSC2767|COSC2805 Systems Deployment and Operations
// Semester: 2026B
// Assessment: Assignment 2
// Author: Vo Hoang Khanh
// ID: s3926310
// Created  date: 14/09/2026
// Last modified: 14/09/2026
// Acknowledgement: Drafted with Claude (Anthropic); the author verified each
//   step by running the same scripts by hand. Reference: Jenkins declarative
//   pipeline syntax, https://www.jenkins.io/doc/book/pipeline/syntax/

// API stages for webapp/Jenkinsfile. Paste the environment entries into the
// existing environment { } block, the stages into stages { }, and the post
// block at pipeline level. Every stage is one script from deploy/bin/, so
// what Jenkins runs is what a laptop runs.
//
// Credentials, by ID:
//   aws-access-key-id, aws-secret-access-key, aws-session-token  (string; Learner Lab, refresh each session)
//   k3s-kubeconfig                                                (secret file; deploy/ansible/k3s.kubeconfig)
//
// Agent needs docker, aws and kubectl on PATH.

environment {
    ECR_API_REPO = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/rmit-store-api"
    TAG          = "${env.GIT_COMMIT.take(7)}"
}

stages {

    stage('API: test') {
        steps {
            sh 'deploy/bin/test.sh $TAG'
        }
        post {
            always {
                junit 'webapp/server/test-reports/junit.xml'
            }
        }
    }

    stage('API: build and push') {
        steps {
            withCredentials([
                string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY'),
                string(credentialsId: 'aws-session-token',     variable: 'AWS_SESSION_TOKEN')
            ]) {
                sh 'ECR_REPO=$ECR_API_REPO deploy/bin/build-push.sh $TAG'
            }
        }
    }

    stage('API: deploy staging') {
        steps {
            withCredentials([
                string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY'),
                string(credentialsId: 'aws-session-token',     variable: 'AWS_SESSION_TOKEN'),
                file(credentialsId: 'k3s-kubeconfig',          variable: 'KUBECONFIG')
            ]) {
                sh 'ECR_REPO=$ECR_API_REPO deploy/bin/deploy.sh staging $TAG'
                sh 'deploy/bin/smoke.sh staging $TAG'
            }
        }
        post {
            always {
                junit allowEmptyResults: true, testResults: 'webapp/server/test-reports/smoke-staging.xml'
            }
        }
    }

    // Only main reaches prod, and only after staging smoke passed above.
    stage('API: deploy prod') {
        when {
            anyOf { branch 'main'; expression { env.GIT_BRANCH == 'origin/main' } }
        }
        steps {
            withCredentials([
                string(credentialsId: 'aws-access-key-id',     variable: 'AWS_ACCESS_KEY_ID'),
                string(credentialsId: 'aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY'),
                string(credentialsId: 'aws-session-token',     variable: 'AWS_SESSION_TOKEN'),
                file(credentialsId: 'k3s-kubeconfig',          variable: 'KUBECONFIG')
            ]) {
                sh 'ECR_REPO=$ECR_API_REPO deploy/bin/deploy.sh prod $TAG'
                sh 'deploy/bin/smoke.sh prod $TAG'
            }
        }
        post {
            always {
                junit allowEmptyResults: true, testResults: 'webapp/server/test-reports/smoke-prod.xml'
            }
        }
    }
}

// Pipeline-level. Any stage going red stops the run before prod and mails the team.
post {
    failure {
        mail to: 'REPLACE_WITH_TEAM_EMAIL',
             subject: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER} (${env.TAG})",
             body: "Stage failed. Console: ${env.BUILD_URL}console"
    }
}

// Optional: a parameterised rollback for prod. Add to parameters { } and stages { }.
//
//   parameters { booleanParam(name: 'API_ROLLBACK_PROD', defaultValue: false, description: 'Undo the last prod rollout') }
//
//   stage('API: rollback prod') {
//       when { expression { params.API_ROLLBACK_PROD } }
//       steps {
//           withCredentials([file(credentialsId: 'k3s-kubeconfig', variable: 'KUBECONFIG')]) {
//               sh 'deploy/bin/rollback.sh prod'
//           }
//       }
//   }
