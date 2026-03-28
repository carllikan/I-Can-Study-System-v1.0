#!/bin/bash

# Define the registry and repository
REGISTRY="gcr.io"
PROJECT="ics-analysis-prod"
REPOSITORYS=("evaluation_api" "final_feedback" "global_search_api" "mind_map_evaluation_api" "mind_map_evaluation_pipeline" "reflection_evaluation_api" "reflection_evaluation_pipeline")

for REPOSITORY in "${REPOSITORYS[@]}"; do
    # Fetch all the images in the repository
    IMAGES_TO_DELETE=$(gcloud container images list-tags "gcr.io/${PROJECT}/${REPOSITORY}" --format=json | jq -r '.[] | select(any(.tags[]?; . == "latest") | not) | .digest')

    # Loop through each image and delete it if it doesn't have the 'latest' tag
    for IMAGE in $IMAGES_TO_DELETE; do
        echo "Deleting image: ${IMAGE}"
        gcloud container images delete -q --force-delete-tags "${REGISTRY}/${PROJECT}/${REPOSITORY}@${IMAGE}"
    done
done

echo "Cleanup completed."