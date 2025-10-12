export SERVER_VERSION=$(cat src/__version__.py | cut -d '=' -f2 | xargs)
source .env
gcloud builds submit --region=${GCP_REGION} --substitutions=_SERVER_VERSION=${SERVER_VERSION},_IMAGE_NAME=${IMAGE_NAME},_GCP_REGION=${GCP_REGION},_REPO_NAME=${REPO_NAME},_PROJECT_ID=${PROJECT_ID} --config imagebuild.yaml
# sed -r 's/SERVER_VERSION/'"$SERVER_VERSION"'/' imagebuild.yaml > container_versioned.yaml
gcloud run deploy ${SERVER_NAME} --image ${GCP_REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${SERVER_VERSION}