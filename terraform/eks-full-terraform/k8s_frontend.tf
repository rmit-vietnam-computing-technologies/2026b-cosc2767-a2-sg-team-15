resource "kubernetes_deployment_v1" "frontend" {
  metadata {
    name = "frontend-deploy"
  }

  spec {
    replicas = var.frontend_replicas

    selector {
      match_labels = {
        app = "frontend"
      }
    }

    template {
      metadata {
        labels = {
          app = "frontend"
        }
      }

      spec {
        container {
          name  = "frontend"
          image = var.frontend_image

          port {
            container_port = var.frontend_container_port
          }
        }
      }
    }
  }

  depends_on = [aws_eks_node_group.devops_workers]
}

resource "kubernetes_service_v1" "frontend" {
  metadata {
    name = "frontend-service"
  }

  spec {
    selector = {
      app = "frontend"
    }

    port {
      port        = 80
      target_port = var.frontend_container_port
    }

    type = "ClusterIP"
  }
}

resource "kubernetes_deployment_v1" "frontend_canary" {
  metadata {
    name = "frontend-canary-deploy"
  }

  spec {
    replicas = var.canary_replicas

    selector {
      match_labels = {
        app = "frontend-canary"
      }
    }

    template {
      metadata {
        labels = {
          app = "frontend-canary"
        }
      }

      spec {
        container {
          name  = "frontend"
          image = var.frontend_canary_image

          port {
            container_port = var.frontend_container_port
          }
        }
      }
    }
  }

  depends_on = [aws_eks_node_group.devops_workers]
}

resource "kubernetes_service_v1" "frontend_canary" {
  metadata {
    name = "frontend-canary-service"
  }

  spec {
    selector = {
      app = "frontend-canary"
    }

    port {
      port        = 80
      target_port = var.frontend_container_port
    }

    type = "ClusterIP"
  }
}
