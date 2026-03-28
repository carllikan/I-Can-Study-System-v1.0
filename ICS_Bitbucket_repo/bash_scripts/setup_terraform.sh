#!/bin/bash

# Exit on any error

set -euo pipefail
set -x

# Terraform initialize 
cd $BITBUCKET_CLONE_DIR/$T_FOLDER/
# Assumes that this is the first deployment check the terraform state file
# This sets the state bucket based on the project ID
export BUCKET="$PROJECT-$T_FOLDER-state"
echo "terraform state bucket to... ${BUCKET}"
# Checking to see if terraform state file bucket is set up and setup if necessary
if gsutil ls | grep -q $BUCKET; then
     echo "Bucket $BUCKET already exists."
#-     export first_deployment=0
else
     echo "Bucket ${BUCKET} does not exists. First time run"
     gsutil mb "gs://$BUCKET"
#-     export first_deployment=1
fi