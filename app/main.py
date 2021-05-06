import json
import os
import tempfile
import numpy as np

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

class UserAOI(BaseModel):
    feature: str
    container_nm: str
    blob_nm: str
app = FastAPI()

# global variable to store container and blob names for user's session
instance_names = {}

# set up a TiTiler endpoint to generate web map tiles from COGs
cog = TilerFactory()
app.include_router(cog.router, tags=["Cloud Optimized GeoTIFF"])
add_exception_handlers(app, DEFAULT_STATUS_CODES)

@app.get("/test")
def test():
    return("OK")

# end point to receive an aoi from user to predict temperature change
@app.post("/upload")
def predict_temperature_chance(user_aoi: UserAOI):

    # Azure setup
    connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    
    # path to public readable cog on azure
    #cog_path = "file:///Users/00094708/Dropbox (Personal)/work/uwa/research/natgeo-ai/natgeo-temp-webmap/cog/mc_1000_byte_cog.tif"
    cog_path = "https://webmapbaselayer.blob.core.windows.net/baselayer/mc_1000_byte_cog.tif"
    
    # temporary file to store cog of temperature change prediction
    tmp_cog = tempfile.NamedTemporaryFile()
    
    # user supplied aoi
    from_user = user_aoi.dict()
    feature = json.loads(from_user["feature"])

    # store temporary container and blob for user's session 
    # store container and blob names in global variable for clean up on shutdown
    global instance_names 
    instance_names["container_name"] = from_user["container_nm"]
    instance_names["blob_name"] = from_user["blob_nm"]

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
        # blob_service_client = BlobServiceClient.from_connection_string(connect_str)

        # # Create the container
        # container_client = blob_service_client.create_container(tmp_container_name, public_access="blob")
        # # Create a blob client using the local file name as the name for the blob
        # blob_client = blob_service_client.get_blob_client(container=tmp_container_name, blob=tmp_blob_name)
        
        # # Upload the created file
        # with open(tmp_cog.name, "rb") as data:
        #     blob_client.upload_blob(data)

    # change response string to url of COG with temperature predictions
    response = {}
    response["min"] = pred_min
    response["max"] = pred_max
    return(response)  