# Kubernetes Deployment Guide

## Resources

- namespace.yaml: Creates the webgis-k8s namespace.
- webgis-client-configmap.json: Preserves the currently deployed client HTML.
- postgis-statefulset.yaml: PostGIS StatefulSet, Services and persistent volume.
- postgis-emptydir.yaml: Temporary-storage Deployment for Q11.
- client-deployment.yaml: Nginx WebGIS client and Service.

## Fresh-cluster deployment

### 1. Create the namespace

    kubectl apply -f k8s/namespace.yaml

### 2. Create the PostgreSQL Secret

Create a local file named `k8s/postgres-secret.env` containing:

    POSTGRES_USER=webgis_user
    POSTGRES_PASSWORD=YOUR_STRONG_PASSWORD
    POSTGRES_DB=webgis_k8s

Replace the password placeholder with a strong password.

Create the Secret:

    kubectl create secret generic postgres-secret --namespace webgis-k8s --from-env-file=k8s/postgres-secret.env

Delete the local plaintext file after successful Secret creation:

    Remove-Item k8s/postgres-secret.env

Never commit or share the plaintext Secret file.

### 3. Apply the client ConfigMap

    kubectl apply -f k8s/webgis-client-configmap.json

### 4. Apply the remaining resources

    kubectl apply -f k8s/postgis-statefulset.yaml
    kubectl apply -f k8s/postgis-emptydir.yaml
    kubectl apply -f k8s/client-deployment.yaml

### 5. Verify resources

    kubectl get pods,services,pvc -n webgis-k8s

### 6. Access the client

    kubectl port-forward service/webgis-client 8087:80 -n webgis-k8s

Open http://localhost:8087.

## Storage behaviour

The PostGIS StatefulSet uses a 1 GiB PersistentVolumeClaim. Its data survives pod replacement.

The separate postgis-emptydir Deployment uses temporary emptyDir storage. Its data is lost when the pod is replaced.

Do not delete the StatefulSet PVC during persistence testing.

## Security

The PostgreSQL Secret is created locally and is not committed to Git. Never commit passwords or decoded Kubernetes Secret values.
