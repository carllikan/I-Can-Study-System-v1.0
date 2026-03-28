#!/bin/bash

# Exit on any error
set -euo pipefail
set -x

# Setting Paths
export PATH="$BITBUCKET_CLONE_DIR:$PATH"

# Authentication with service account
echo "Authenticating with service account..."
echo "$SERVICE_ACCOUNT_EMAIL"
echo $KEY_FILE | base64 -di >> /tmp/key-file.json  
gcloud auth activate-service-account $SERVICE_ACCOUNT_EMAIL --key-file /tmp/key-file.json --project $PROJECT

# Configuring gcloud settings
echo "Setting region to... ${REGION}"
gcloud config set run/region $REGION

echo "Setting project to... ${PROJECT}"
gcloud config set project $PROJECT

# Export Google Application Credentials path
export GOOGLE_APPLICATION_CREDENTIALS="/tmp/key-file.json"
