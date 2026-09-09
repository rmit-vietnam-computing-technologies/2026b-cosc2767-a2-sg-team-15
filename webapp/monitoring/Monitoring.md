# RMIT Store Monitoring and Alerting

## Integration placeholders
The dashboard currently uses the planned Prometheus job name:

    rmit-store-django

This is a logical monitoring job name, not the final Kubernetes Service name.

The following values remain pending from the EKS/containerization workstream:

- Kubernetes namespace
- Backend Deployment name
- Backend Service name
- Backend Service port
- Backend Service targetPort
- Backend Service port name
- Backend pod labels/selectors
## Objective

Provide real-time visibility into application, Kubernetes and deployment health,
and notify the team when runtime failures or performance degradation occur.

## Monitoring stack

The monitoring stack will use kube-prometheus-stack on Kubernetes.

Components:

- Prometheus — metrics collection and querying
- Grafana — dashboards and visualization
- Alertmanager — alert routing and notification
- kube-state-metrics — Kubernetes object/state metrics
- node-exporter — node-level resource metrics

## Monitoring layers

### 1. Kubernetes infrastructure

- Node CPU and memory
- Pod CPU and memory
- Pod restart counts
- Deployment replica availability
- Kubernetes workload health

### 2. Django application

- HTTP request rate
- HTTP response status
- HTTP 5xx error rate
- Request latency
- Django/process metrics
- Database-related metrics exposed by django-prometheus

### 3. Application health

- `/healthz/` — liveness
- `/readyz/` — readiness
- `/api/version/` — running build identification

### 4. Deployment

Deployment verification will use `/api/version/` together with health and
performance metrics.

## Current limitation

The EKS deployment has not yet been finalized. Kubernetes Service names,
namespaces, ports and labels will be added after the containerization/EKS
workstream is completed.

## Future integration

Prometheus will use a ServiceMonitor to scrape the Django Kubernetes Service
at `/metrics`.

## Alerting strategy

The monitoring system separates runtime failures from CI/CD failures.

### CI/CD failures

Jenkins is responsible for failures during:
- build
- test
- image creation
- deployment

These failures are handled by the CI/CD pipeline and its notification mechanism.

### Runtime failures

Prometheus and Alertmanager are responsible for:
- backend unavailability
- high HTTP 5xx error rates
- excessive response latency
- database errors
- Kubernetes workload failures

Runtime alerts are evaluated continuously after deployment.

## Production WSGI consideration

The Django application is currently instrumented with django-prometheus.
The final Prometheus export configuration must be verified against the
production Gunicorn worker model because django-prometheus documents special
handling for multi-process WSGI deployments.

The final Gunicorn configuration is owned by the backend/containerization
workstream and will be integrated before production deployment.

## Kubernetes integration

The final Prometheus scrape target will use a Kubernetes ServiceMonitor.

The following values are intentionally not fixed yet because the EKS/containerization
workstream has not finalized the backend Service:

- Kubernetes namespace
- Django Service name
- Service port/name
- backend Service labels/selectors

Required endpoint:

    /metrics/

Once the backend Deployment and Service are available, the monitoring workstream
will add the corresponding ServiceMonitor.