from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from PIL import Image
import torch, logging

logger = logging.getLogger("app")

model = VisionEncoderDecoderModel.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
feature_extractor = ViTImageProcessor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

max_length = 16
num_beams = 4
gen_kwargs = {"max_length": max_length, "num_beams": num_beams}

# Calling of function should follow this format: predict_caption(['<FileName>.<Extension>'])
def predict_caption(image_paths):

    images = []
    image_path = []

    if isinstance(image_path, str):
        image_path = [image_paths]

    logger.info(f"CAPTION_MODEL_START - num_images={len(image_paths)}")

    for image_path in image_paths:
        try:
            i_image = Image.open(image_path)

            if i_image.mode != "RGB":
                i_image = i_image.convert(mode = "RGB")
            
            images.append(i_image)

        # User enters a wrong file name or file does not exist...
        except FileNotFoundError:
            logger.error(f"FILE_NOT_PRESENT - File not found: {image_path}")

        # All other errors...
        except Exception as e:
            logger.error(f"ERR_UNABLE_TO_OPEN_IMAGE - Error opening image: {image_path} => {e}")

    try:
        pixel_values = feature_extractor(
            images = images, 
            return_tensors = "pt"
        ).pixel_values.to(device)

        output_ids = model.generate(pixel_values, **gen_kwargs)

        preds = tokenizer.batch_decode(output_ids, skip_special_tokens = True)
        preds = [pred.strip() for pred in preds]

        logger.info("CAPTION_MODEL_DONE")

        return preds    # Returns the AI caption in a list...
    
    # General Model Errors
    except Exception as e:
        logger.error(f"CAPTION_ERR - Model inference failed: {e}")