# Import Modules
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import os
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Dict

# 
class Thumbnails(BaseModel):
    small: str
    medium: str

class ImageData(BaseModel):
    image_id: str
    original_name: str
    processed_at: str
    metadata: dict[str, str]
    thumbnails: Thumbnails

class ImageResponse(BaseModel):
    status: str = ""
    data: Optional[ImageData] = None
    error: str = None

# Global Variables
images = []
err_counter = 0 # Counts the no. of errors (resets everytime the server reloads)
success_rate = 0.0 # 0.5 * (no. of successful entries / total no. of entries)
average_processing_time_seconds = 0 # readjusts everytime a new entry is added
UPLOAD_DIR = "uploads" # Directory to store file uploads

app = FastAPI()
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Generates directory if not already generated

@app.get("/api")
def root():
    return {"Hello": "World"}

# Function 1: Processing Input (JPG / PNG files types only)
@app.post("/api/images", response_model = ImageResponse)
async def upload_image(file: UploadFile = File(...)):
    try:
        timestamp = datetime.utcnow().strftime("%H:%M:%S %d:%m:%Y")
        file_location = os.path.join(UPLOAD_DIR, f"{timestamp}_{file.filename}")

        with open(file_location, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        return images
        # return JSONResponse({
        #     "status": "Success",
        #     "data": {
        #         "filename": file.filename,
        #         "stored-as": file_location
        #     }
        # })
    
    except Exception as e:
        return JSONResponse({
            "status": "Failed",
            "error": str(e)
        }, status_code = 500)
    
# Function 2: Returns a list of processed images 
@app.get("/api/images", response_model = list[ImageResponse])
def image_main():
    return images

# Function 3: Returns a image object
@app.get("/api/images/{id}", response_model = ImageResponse)
def get_specific_image():
    return {}

# Function 4: Returns a specific image detail
@app.get("/api/images/{id}/thumbnail/{size}")
def get_specific_size_image():
    return {}

# Function 5: Returns statistics of images
@app.get("/api/stats")
def get_overall_status():
    return {}