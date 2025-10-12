export DAYLIGHT_SERVER_VERSION=$(cat src/__version__.py | cut -d '=' -f2 | xargs)
source .env
# scw registry namespace create name=${SCW_REGISTRY_NAMESPACE} project-id=${SCW_PROJECT_ID}
docker build -t rg.fr-par.scw.cloud/${SCW_SERVER}/${SCW_IMAGE}:${DAYLIGHT_SERVER_VERSION} .
docker push rg.fr-par.scw.cloud/${SCW_SERVER}/${SCW_IMAGE}:${DAYLIGHT_SERVER_VERSION}
# Försök hitta containern. -o json ger utdata som JSON. jq -e kollar om det 
NAMESPACE_ID=$(scw container namespace list --output json | jq -r '.[0].id')

CONTAINER_ID=$(scw container container list name=$SCW_SERVE_CONTAINER_NAME namespace-id=$NAMESPACE_ID --output json | jq -e '.[0].id' 2>/dev/null)

CONTAINER_INFO=$(scw container container list name=$SCW_SERVE_CONTAINER_NAME namespace-id=$NAMESPACE_ID --output json 2>/dev/null)
CONTAINER_EXISTS=$(echo "$CONTAINER_INFO" | jq -e '.[0] != null')

if [ "$CONTAINER_EXISTS" == "true" ]; then
    CONTAINER_ID=$(echo "$CONTAINER_INFO" | jq -r '.[0].id')
    CONTAINER_STATUS=$(echo "$CONTAINER_INFO" | jq -r '.[0].status')
    
    echo "Containern '$SCW_SERVE_CONTAINER_NAME' hittades med status: $CONTAINER_STATUS"

    if [ "$CONTAINER_STATUS" == "error" ]; then
        echo "Containern är i ett felaktigt tillstånd. Raderar och återskapar..."
        scw container container delete "$CONTAINER_ID" --wait
        echo "Skapar en ny container..."
        scw container container create name=$SCW_SERVE_CONTAINER_NAME namespace-id=$NAMESPACE_ID registry-image=rg.fr-par.scw.cloud/${SCW_SERVER}/${IMAGE_NAME}:${DAYLIGHT_SERVER_VERSION}
    else
        echo "Uppdaterar befintlig container..."
        scw container container deploy "$CONTAINER_ID"
    fi
else
      echo "Containern '$SCW_SERVE_CONTAINER_NAME' hittades inte. Skapar ny..."
  scw container container create name=$SCW_SERVE_CONTAINER_NAME namespace-id=$NAMESPACE_ID registry-image=rg.fr-par.scw.cloud/${SCW_SERVER}/${IMAGE_NAME}:${DAYLIGHT_SERVER_VERSION}
fi

# echo "Container ID: $CONTAINER_ID"
# if [ $? -eq 0 ]; then
#   echo "Containern '$SCW_SERVE_CONTAINER_NAME' hittades. Uppdaterar..."
#   scw container container deploy ${CONTAINER_ID}
# else
  # echo "Containern '$SCW_SERVE_CONTAINER_NAME' hittades inte. Skapar ny..."
  # scw container container create name=$SCW_SERVE_CONTAINER_NAME namespace-id=$NAMESPACE_ID registry-image=rg.fr-par.scw.cloud/${SCW_SERVER}/${IMAGE_NAME}:${DAYLIGHT_SERVER_VERSION}
# fi
