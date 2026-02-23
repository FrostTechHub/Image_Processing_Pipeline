# Import Modules
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional, Dict
from PIL import Image
from PIL.ExifTags import TAGS
from time import perf_counter
from hugging_face import predict_caption
from enum import Enum
from typing import Any
import string, random, os, asyncio, logging

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
    processed_at: str = ""
    metadata: Optional[Metadata] = None
    exif_data: Optional[dict] = None
    ai_caption: str = ""
    thumbnails: Optional[Thumbnails] = None

class ImageResponse(BaseModel):
    status: str = ""
    data: Optional[ImageData] = None
    error: Optional[str] = None

class Stats(BaseModel):
    total: int
    failed: int
    success_rate: str
    average_processing_time_seconds: float

class JobStatus(str, Enum):
    queued: str = "queued"
    processing: str = "processing"
    success: str = "success"
    failed: str = "failed"

# Global Variables
images: Dict[str, ImageResponse] = {}
ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png"]
entry_counter = 0
fail_counter = 0 # Counts the no. of errors (resets everytime the server reloads)
succ_counter = 0 
total_process_time_sec = 0 # Updates after every entry...
API_IMAGES_ROUTES = "/api/images"
PRIMARY_DIR = os.path.join("api", "images")
SECONDARY_DIR = os.path.join("api", "stats")

job_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
os.makedirs(PRIMARY_DIR, exist_ok=True)  # Generates directory if not already generated

# Configure Logging Settings...
logging.basicConfig(filename="app.log", level=logging.DEBUG, filemode="a", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("app")

app = FastAPI()

# Track the start time taken 
def start_time():
    return perf_counter()

# Track the start time taken
def end_time(start):
    global total_process_time_sec

    elapsed = (perf_counter() - start)
    total_process_time_sec += elapsed

# Calculate average processing time
def calc_average_time() -> float:
    global total_process_time_sec, entry_counter

    if (entry_counter == 0):
        return 0.0

    return round(total_process_time_sec / entry_counter, 1)

# Calculate success rate
def calc_suc_rate() -> str:
    global succ_counter, entry_counter, fail_counter

    if (entry_counter == 0):
        return f"0.00%"

    return f"{(succ_counter / entry_counter) * 100:.2f}"

# Functions Declaration
# Verify upload is jpg or png only
def verify_file_type(filename: str) -> bool:
    try:
        with Image.open(filename) as ft:
            format = (ft.format or "").lower()    # Extract file type        
        return format in ALLOWED_EXTENSIONS # Verify if file format is in list of allowed extensions
    
    except Exception:
        logger.info("FILE_EXTENSION_INVALID - Client has uploaded an file with an invalid file extension.")
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

def get_img_EXIFData(image_path: str) -> dict:

    data_dict = {}
    img = Image.open(image_path)
    exifData = img.getexif()    # Extract the exif data

    # Loop through all the tags present in exifdata
    for tagid in exifData:
        tagName = TAGS.get(tagid, tagid)    # Retrieving tag name instead of tag id
        value = exifData.get(tagid)         # Passing the tag id to get respective value
        data_dict[tagName] = value

    if len(data_dict) == 0:
        logger.info("NON_EXISTENT_DATA - File appears to contain NO EXIF Data.")
        data_dict["info"] = "No EXIF Data to extract"

    return data_dict

# Generate Thumbnails object
def get_img_thumbnail(file_path: str, img_id: str):

    return Thumbnails(
        small = generate_img_thumbnail_sizes(file_path, True, img_id), 
        medium = generate_img_thumbnail_sizes(file_path, False, img_id)
        )

# Generate Thumbnails Sizes
def generate_img_thumbnail_sizes(image_path: str, small: bool, img_id: str):

    logger.debug(f"THUMBNAIL_GENERATING - img_id : {img_id}, small? : {small}")

    image = Image.open(image_path)

    # Converter for PNG images...
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    if small == True:
        size = (128, 128)   # Assign a small pixel size
        suffix = "small"
    else:
        size = (512, 512)   # Assign a medium pixel size
        suffix = "medium"

    image.thumbnail(size) # Generate thumbnail based on SIZE variable

    # Generate a thumbsnail folder
    thumbnails_folder = os.path.join(PRIMARY_DIR, img_id, "thumbnails")
    os.makedirs(thumbnails_folder, exist_ok=True)

    thumbnails_path = os.path.join(thumbnails_folder, f"{suffix}.jpg")
    
    image.save(thumbnails_path)
    logger.debug(f"THUMBNAIL_SAVED - pathway : {thumbnails_path}")

    return f"http://localhost:8000/api/images/{img_id}/thumbnails/{suffix}"

async def running_loop():
    global succ_counter, fail_counter

    while True:
        logger.debug(f"QUEUE_SIZE_BEFORE_GET - size={job_queue.qsize()}")

        job = await job_queue.get()
        s_t = start_time() # Start Time to calculate processing time
        img_id = job["img_id"]  # Retrieve already generated img id
        file_location = job["file_location"]

        current = images[img_id]
        current.status = JobStatus.processing.value
        images[img_id] = current

        logger.info(f"JOB_PROCESSING_STARTED - img_id : {img_id}, status : {current.status}")

        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            metadata = get_img_metadata(file_location)
            ai_caption = predict_caption([file_location])[0]
            # ai_caption = "Temporarily Disabled"
            exif_data = get_img_EXIFData(file_location)
            thumbnails = get_img_thumbnail(file_location, img_id)

            # Update stored responses
            current.data.processed_at = timestamp
            current.data.ai_caption = ai_caption

            logger.info(f"CAPTION_GENERATED_SUCCESSFUL - img_id{img_id}")

            current.data.metadata = metadata
            current.data.exif_data = exif_data
            current.data.thumbnails = thumbnails

            logger.info(f"THUMBNAILS_CREATED - img_id : {img_id}")

            current.status = JobStatus.success.value
            current.error = None
            images[img_id] = current

            succ_counter += 1

            logger.info(f"JOB_COMPLETED - img_id : {img_id}")

            end_time(s_t)

        except Exception as e:
            end_time(s_t)

            current.status = JobStatus.failed.value
            current.error = str(e)
            images[img_id] = current

            logger.error(f"JOB_FAILED - img_id : {img_id}, error : {current.error}, exc_info=True")

            fail_counter += 1

        finally:
            job_queue.task_done()
            logger.debug(f"QUEUE_SIZE_AFTER_DONE - size={job_queue.qsize()}")

# Routes Declaration
@app.on_event("startup")
async def startup_event():  # First function to run...
    asyncio.create_task(running_loop())

@app.get("/api")
def root():
    return {"Hello": "HTX"}

# Function 1: Processing Input (JPG / PNG files types only)
# Command to run this function: curl.exe -F "file=@{file_name}.{file_extension}" http://127.0.0.1:8000/api/images (POWERSHELL)
@app.post(API_IMAGES_ROUTES, response_model = ImageResponse)
async def upload_image(file: UploadFile = File(...)):
    global fail_counter, entry_counter

    entry_counter += 1

    img_id = generate_new_img_ID()  # Generate img_id
    org_name = file.filename        # Keep original naming of file

    logger.info(f"UPLOAD_RECEIVED - img_id : {img_id}, filename : {org_name}")

    image_folder = os.path.join(PRIMARY_DIR, img_id)
    os.makedirs(image_folder, exist_ok= True) # Make a new folder for every new img_id

    file_location = os.path.join(image_folder, org_name)

    # Saved the file
    with open(file_location, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        logger.debug(f"FILE_SAVED - img_id : {img_id}, pathway : {file_location}")
    
    # Create a base object (no metadata / thumbnails added yet)
    imgData_obj = ImageData(
        image_id = img_id, 
        original_name = org_name, 
        processed_at = "", 
        metadata = None,
        ai_caption = "",
        exif_data = None,
        thumbnails = None
        )
    
    file_valid_result = verify_file_type(file_location)

    # Verify if file extension is of required format
    if verify_file_type(file_location) == False:
        fail_counter += 1   # Update failed counter...
        imgRes_obj = ImageResponse(status = JobStatus.failed.value, data = imgData_obj, error = "Invalid File Format!")

        # Append image responses object into dict
        images[img_id] = imgRes_obj
        return imgRes_obj
    
    logger.info(f"FILE_EXTENSION_VERIFIED - img_id : {img_id}, valid : {file_valid_result}")

    imgRes_obj = ImageResponse(status = JobStatus.queued.value, data = imgData_obj, error = None)
    images[img_id] = imgRes_obj

    logger.info(f"JOB_ENQUEUED - img_id : {img_id}")

    await job_queue.put({
        "img_id" : img_id,
        "file_location" : file_location,
        "org_name" : org_name
    })

    return imgRes_obj
    
# Function 2: Returns a list of processed images 
@app.get("/api/images", response_model = list[ImageResponse])
def return_all_image():
    return list(images.values())

# Function 3: Returns a image object
@app.get("/api/images/{img_id}")
def get_image(img_id: str):

    image_obj = images.get(img_id)

    if image_obj is None:
        return ImageResponse(status = JobStatus.failed.value, data = None, error = "Invalid Image ID - Image does not exists...")

    return image_obj

# Function 4: Returns a specific image detail
@app.get("/api/images/{img_id}/thumbnails/{size}")
def get_thumbnail(img_id: str, size: str):
    
    image_obj = images.get(img_id)

    if image_obj is None:
        logger.warning(f"INVALID_IMAGE_ID - Client has attempted to access a file with an invalid ID (img_id: {images.get(img_id)}).")
        return {"error" : "Image ID Not Found!"}
    
    if image_obj.data.thumbnails is None:
        logger.warning(f"NON_EXISTENT_DATA - Client has attempted to view a file's thumbnail, but file contains no thumbnails (img_id: {images.get(img_id)}).")
        return {"error" : "No Thumbnails Available!"}
    
    if size.lower() not in ["small", "medium"]:
        logger.warning("NON_EXISTENT_SIZING - Client has attempted to view a file's thumbnail, but file "
            + f"does not contain the sizing the user is looking for (img_id: {images.get(img_id)}, requested_size: {size}).")
        return {"error" : "Invalid Thumbnail Sizing..."}
    
    file_pathway = f"api/images/{img_id}/thumbnails/{size}.jpg"

    return FileResponse(file_pathway)

# Function 5: Returns statistics of images
@app.get("/api/stats")
def get_overall_status():
    return Stats(total = entry_counter, failed = fail_counter, success_rate = f"{calc_suc_rate()}%", average_processing_time_seconds = calc_average_time())