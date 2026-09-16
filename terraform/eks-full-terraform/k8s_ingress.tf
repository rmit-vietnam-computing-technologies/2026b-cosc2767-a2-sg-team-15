# The "frontend-weighted" name below is not a real Kubernetes Service - it
# only exists as the key of the alb.ingress.kubernetes.io/actions.* annotation.
# The `use-annotation` port name is a magic value the AWS Load Balancer
# Controller recognizes, meaning "route according to that annotation's
# weighted forward config" rather than looking up a real service port.
resource "kubernetes_ingress_v1" "frontend" {
  metadata {
    name = "frontend-ingress"

    annotations = {
      "kubernetes.io/ingress.class"                = "alb"
      "alb.ingress.kubernetes.io/scheme"           = "internet-facing"
      "alb.ingress.kubernetes.io/target-type"      = "ip"
      "alb.ingress.kubernetes.io/actions.frontend-weighted" = jsonencode({
        type = "forward"
        forwardConfig = {
          targetGroups = [
            {
              serviceName = kubernetes_service_v1.frontend.metadata[0].name
              servicePort = "80"
              weight      = 100 - var.canary_weight
            },
            {
              serviceName = kubernetes_service_v1.frontend_canary.metadata[0].name
              servicePort = "80"
              weight      = var.canary_weight
            }
          ]
        }
      })
    }
  }

  spec {
    rule {
      http {
        path {
          path      = "/"
          path_type = "Prefix"

          backend {
            service {
              name = "frontend-weighted"
              port {
                name = "use-annotation"
              }
            }
          }
        }
      }
    }
  }

  depends_on = [helm_release.aws_load_balancer_controller]
}
