# Predict warming caused by local and non-local forest loss

A FastAPI and Titiler application that predicts warming (surface temperature change) due to local and non-local deforestation in the Maritime Continent of South-East Asia and Oceania.

The application receives a user request specifying an area-of-interest (AOI) and indicator of forest loss fraction and type of loss event (clear felling or fragmented), uses Titiler to obtain forest cover for the AOI, applies a statistical model to predict warming caused by local forest loss and nonlocal (neighbouring forest loss), and finally uses Titiler and rio-tiler to make the predicted warming available as a tiled web map. 

## Setup

Use `pip` to install python packages to generate a requirements.txt that can be used with docker.

Generate the requirements.txt file:

```
pip freeze > requirements.txt
```

## Build 

Build the app image from the Dockerfile:

```
docker build -t cogserver .
```

## Deploy to Azure App Service

Set up Azure Container Registry. One time!

```
az acr create --name myregistry --resource-group mygroup --sku standard --admin-enabled true
```

Upload image to Azure Container Registry. Repeated builds will update the image in Azure Container Registry. The image with tag `latest` will be deployed on app service. 

```
az acr build --registry <container_registry_name> --image cogserver .
```

