# Import Modules
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Dict
from PIL import Image # Generating Thumbnail images
from PIL.ExifTags import TAGS
import string, random, os, hashlib

class Metadata(BaseModel):
    width: int
    height: int
    format: str
    size_bytes: int

class Thumbnails(BaseModel):
    small: Optional[str] = None
    medium: Optional[str] = None

class ImageData(BaseModel):
    image_id: str
    original_name: str
    processed_at: str
    metadata: Optional[Metadata] = None
    thumbnails: Optional[Thumbnails] = None

class ImageResponse(BaseModel):
    status: str = ""
    data: Optional[ImageData] = None
    error: Optional[str] = None

# Global Variables
images = []
ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png"]
err_counter = 0 # Counts the no. of errors (resets everytime the server reloads)
success_rate = 0.0 # 0.5 * (no. of successful entries / total no. of entries)
average_processing_time_seconds = 0 # readjusts everytime a new entry is added
PRIMARY_DIR = "/api/images"
SECONDARY_DIR = "/api/stats"

app = FastAPI()
os.makedirs(PRIMARY_DIR, exist_ok=True)  # Generates directory if not already generated

# Functions Declaration
# Verify upload is jpg or png only
def verify_file_type(filename: str) -> bool:
    try:
        with Image.open(filename) as ft:
            format = (ft.format or "").lower()    # Extract file type        
        return format in ALLOWED_EXTENSIONS # Verify if file format is in list of allowed extensions
    
    except Exception:
        return False

# Generate Unique Image IDs
def generate_new_img_ID(length=3):

    # Generate an img ID starting with 'img' + 3 digits...
    return f"img" + ''.join(random.choice(string.digits) for i in range(length))

# Gather metadata from img
def get_img_metadata(image_path: str):

    _size_bytes = os.path.getsize(image_path) # Retrieve the image byte size

    # Extract image width, height, format
    with Image.open(image_path) as img:
        _width, _height = img.size
        _format = img.format

    return Metadata(width = _width, height = _height, format = _format, size_bytes = _size_bytes)

# Generate Thumbnails object
def get_img_thumbnail(file_path: str, img_id: str):

    return Thumbnails(
        small = generate_img_thumbnail_sizes(file_path, True, img_id), 
        medium = generate_img_thumbnail_sizes(file_path, False, img_id)
        )

# Generate Thumbnails Sizes
def generate_img_thumbnail_sizes(image_path: str, small: bool, img_id: str):
    image = Image.open(image_path)

    # Converter for PNG images...
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    if small == True:
        SIZE = (128, 128)   # Assign a small pixel size
        SUFFIX = "small"
    else:
        SIZE = (512, 512)   # Assign a medium pixel size
        SUFFIX = "medium"

    image.thumbnail(SIZE) # Generate thumbnail based on SIZE variable

    # Generate a thumbsnail folder
    thumbnails_folder = os.path.join("api/images", img_id, "thumbnails")
    os.makedirs(thumbnails_folder, exist_ok=True)

    thumbnails_path = os.path.join(thumbnails_folder, f"{SUFFIX}.jpg")
    
    image.save(thumbnails_path)

    return f"http://localhost:8000/api/images/{img_id}/thumbnails/{SUFFIX}"

# Verifies if the image response object is inside the images list
def does_img_exist(img_id: str) -> object:
    for img in images:
        if (img.data.image_id == img_id):
            return img

# Routes Declaration
@app.get("/api")
def root():
    return {"Hello": "World"}

# Function 1: Processing Input (JPG / PNG files types only)
# Command to run this function: curl.exe -F "file=@{file_name}.{file_extension}" http://127.0.0.1:8000/api/images (POWERSHELL)
@app.post(PRIMARY_DIR, response_model = ImageResponse)
async def upload_image(file: UploadFile = File(...)):
    try:
        img_id = generate_new_img_ID()  # Generate img_id
        org_name = file.filename        # Keep original naming of file

        image_folder = os.path.join(PRIMARY_DIR.strip("/"), img_id)
        os.makedirs(image_folder, exist_ok= True) # Make a new folder for every new img_id

        file_location = os.path.join(image_folder, org_name)

        # Saved the file
        with open(file_location, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") # When the file has finished 'processing'
        
        # Create a base object (no metadata / thumbnails added yet)
        imgData_obj = ImageData(
            image_id = img_id, 
            original_name = org_name, 
            processed_at = timestamp, 
            metadata = None, 
            thumbnails = None
            )
        
        # Verify if file extension is of required format
        if verify_file_type(file_location) == False:

            imgRes_obj = ImageResponse(status = "Failed", data = imgData_obj, error = "Invalid File Format!")

            # Append image responses object into list
            images.append(imgRes_obj)

            return imgRes_obj
        
        else:
            imgData_obj.metadata = get_img_metadata(file_location)
            imgData_obj.thumbnails = get_img_thumbnail(file_location, img_id)

            imgRes_obj = ImageResponse(status = "Success", data = imgData_obj, error = None)
            
            # Append image responses object into list
            images.append(imgRes_obj)

            return imgRes_obj
    
    except Exception as e:
        return ImageResponse(status = "Failed", data = None, error = str(e))
    
# Function 2: Returns a list of processed images 
@app.get("/api/images", response_model = list[ImageResponse])
def return_all_image():
    return images

# Function 3: Returns a image object
@app.get("/api/images/{img_id}")
def get_image(img_id: str):

    image_obj = does_img_exist(img_id)

    if image_obj is None:
        return {"error" : "Image ID Not Found!"}

    return image_obj

# Function 4: Returns a specific image detail
@app.get("/api/images/{img_id}/thumbnails/{size}")
def get_thumbnail(img_id: str, size: str):
    
    image_obj = does_img_exist(img_id)

    if image_obj is None:
        return {"error" : "Image ID Not Found!"}
    
    if image_obj.data.thumbnails is None:
        return {"error" : "No Thumbnails Available!"}
    
    if size.lower() == "small":
        url = image_obj.data.thumbnails.small
    elif size.lower() == "medium":
        url = image_obj.data.thumbnails.medium
    else:
        return {"error" : "Invalid Thumbnail Sizing..."}
    
    file_pathway = f"api/images/{img_id}/thumbnails/{size}.jpg"

    return FileResponse(file_pathway)

# Function 5: Returns statistics of images
@app.get("/api/stats")
def get_overall_status():
    return {}