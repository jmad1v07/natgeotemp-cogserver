import json
import os
import tempfile
import numpy as np
from scipy.ndimage.filters import convolve

from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers

from rio_tiler.io import COGReader
from rio_tiler.profiles import img_profiles
from rio_tiler.models import ImageData, Metadata
from rio_tiler.colormap import cmap

from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

import rasterio
from rasterio.io import MemoryFile

from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, __version__

from fastapi import FastAPI
from pydantic import BaseModel

from pydantic import BaseSettings

class Settings(BaseSettings):
    az_str: str 
    cog_path: str

    class Config:
        env_file = ".env"

settings = Settings()

class UserAOI(BaseModel): 
    feature: str
    container_nm: str
    blob_nm: str
    deforestation_amount: float
    deforestation_type: str

class CleanUp(BaseModel):
    container_nm: str


app = FastAPI()

# set up a TiTiler endpoint to generate web map tiles from COGs
cog = TilerFactory()
app.include_router(cog.router, tags=["Cloud Optimized GeoTIFF"])
add_exception_handlers(app, DEFAULT_STATUS_CODES)

@app.get("/test")
def test():
    return("OK")

# end point to receive an aoi from user to predict temperature change
@app.post("/upload")
def predict_temperature_change(user_aoi: UserAOI):

    # Azure setup
    connect_str = settings.az_str

    # path to public readable cog on azure
    cog_path = settings.cog_path
    
    # temporary file to store cog of temperature change prediction
    tmp_cog = tempfile.NamedTemporaryFile()
    
    # user supplied aoi
    from_user = user_aoi.dict()
    feature = json.loads(from_user["feature"])

    # store temporary container and blob for user's session
    tmp_container_name = from_user["container_nm"]
    tmp_blob_name = from_user["blob_nm"]

    # read raster data clipped to user's aoi
    with COGReader(cog_path) as cog:
        # we use the feature to define the bounds and the mask
        img = cog.feature(feature)

    # do temperature prediction here
    img1 = ((img.data / 255) + 30)

    img.data = img1  

    # get prediction min and max values to rescale data and send to client for rendering legend
    pred_min = np.min(img.data)
    pred_max = np.max(img.data)

    # Rescale the data linearly from 30 - 31 to 0-255 and convert to byte format
    img = img.post_process(in_range=(pred_min, pred_max))

    # Get Colormap
    cm = cmap.get("ylorrd")

    # write output of simulation of user's deforestation event to COG
    src_profile = dict(
        driver="GTiff",
        dtype="uint8",
        count=img.count,
        height=img.height,
        width=img.width,
        crs="epsg:4326",
        transform=img.transform
        )
    
    # write COG to temporary file
    # write temporary file as blob in azure storage container
    with MemoryFile() as memfile:
        with memfile.open(**src_profile) as mem:
            # Populate the input file with numpy array
            mem.write(img.data)
            dst_profile = cog_profiles.get("deflate")
            cog_translate(
                mem,
                tmp_cog.name, 
                dst_profile,
                in_memory=True,
                quiet=True,
                web_optimized=True,
                nodata=0,
                colormap=cm,
            )
        # Create the BlobServiceClient object which will be used to create a container client
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)

        out_list = []
        container_list = blob_service_client.list_containers()
        for cont in container_list:
            out_list.append(cont["name"])

        if tmp_container_name not in out_list:
            # Create the container
            container_client = blob_service_client.create_container(tmp_container_name, public_access="blob")

        # Create a blob client using the local file name as the name for the blob
        blob_client = blob_service_client.get_blob_client(container=tmp_container_name, blob=tmp_blob_name + ".tif")
        
        # Upload the created cog file and overwrite
        with open(tmp_cog.name, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

    # change response string to url of COG with temperature predictions
    response = {}
    cog_prediction_url = "https://webmapbaselayer.blob.core.windows.net/" + tmp_container_name + "/" + tmp_blob_name + ".tif"
    response["min"] = pred_min
    response["max"] = pred_max
    response["pred_url"] = cog_prediction_url
    return(response)  

@app.post("/cleanup")
def clean_up(cleanup: CleanUp):
    # Azure setup
    connect_str = settings.az_str
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)

    from_user = cleanup.dict() 
    tmp_container_name = from_user["container_nm"]

    delete_list = []
    container_list = blob_service_client.list_containers()
    for cont in container_list:
        delete_list.append(cont["name"])
    
    if tmp_container_name in delete_list:
        container_client = blob_service_client.get_container_client(tmp_container_name)
        container_client.delete_container()
        print("deleted: " + tmp_container_name)



