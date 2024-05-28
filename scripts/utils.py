import torch
from ultralytics import YOLO
from transformers import SamModel, SamProcessor
import numpy as np
from PIL import Image, ImageOps
from config import SEGMENTATION_MODEL_NAME, DETECTION_MODEL_NAME
from diffusers.utils import load_image
import gc







def clear_memory():
    """
    Clears the memory by collecting garbage and emptying the CUDA cache.

    This function is useful when dealing with memory-intensive operations in Python, especially when using libraries like PyTorch.

   """
    gc.collect()
    torch.cuda.empty_cache()
   




def accelerator():
    """
    Determines the device accelerator to use based on availability.

    Returns:
        str: The name of the device accelerator ('cuda', 'mps', or 'cpu').
    """
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    else:
        return "cpu"

class ImageAugmentation:
    """
    Class for centering an image on a white background using ROI.

    Attributes:
        target_width (int): Desired width of the extended image.
        target_height (int): Desired height of the extended image.
        roi_scale (float): Scale factor to determine the size of the region of interest (ROI) in the original image.
    """

    def __init__(self, target_width, target_height, roi_scale=0.6):
        self.target_width = target_width
        self.target_height = target_height
        self.roi_scale = roi_scale

    def extend_image(self, image: Image) -> Image:
        """
        Extends an image to fit within the specified target dimensions while maintaining the aspect ratio.
        """
        original_width, original_height = image.size
        scale = min(self.target_width / original_width, self.target_height / original_height)
        new_width = int(original_width * scale * self.roi_scale)
        new_height = int(original_height * scale * self.roi_scale)
        resized_image = image.resize((new_width, new_height))
        extended_image = Image.new("RGB", (self.target_width, self.target_height), "white")
        paste_x = (self.target_width - new_width) // 2
        paste_y = (self.target_height - new_height) // 2
        extended_image.paste(resized_image, (paste_x, paste_y))
        return extended_image

    def generate_mask_from_bbox(self,image: Image, segmentation_model: str ,detection_model) -> Image:
        """
        Generates a mask from the bounding box of an image using YOLO and SAM-ViT models.

        Args:
            image_path (str): The path to the input image.

        Returns:
            numpy.ndarray: The generated mask as a NumPy array.
        """
    
        yolo = YOLO(detection_model)
        processor = SamProcessor.from_pretrained(segmentation_model)
        model = SamModel.from_pretrained(segmentation_model).to(device=accelerator())
        results = yolo(image)
        bboxes = results[0].boxes.xyxy.tolist()
        input_boxes = [[[bboxes[0]]]]
        inputs = processor(load_image(image), input_boxes=input_boxes, return_tensors="pt").to("cuda")
        with torch.no_grad():
            outputs = model(**inputs)
        mask = processor.image_processor.post_process_masks(
            outputs.pred_masks.cpu(),
            inputs["original_sizes"].cpu(),
            inputs["reshaped_input_sizes"].cpu()
        )[0][0][0].numpy()
        mask_image = Image.fromarray(mask)
        return mask_image



    def invert_mask(self, mask_image: np.ndarray) -> np.ndarray:
        """
        Inverts the given mask image.
        """
        
        
        inverted_mask_pil = ImageOps.invert(mask_image.convert("L"))
        return inverted_mask_pil

if __name__ == "__main__":
    augmenter = ImageAugmentation(target_width=1024, target_height=1024, roi_scale=0.5)
    image_path = "../sample_data/example3.jpg"
    image = Image.open(image_path)
    extended_image = augmenter.extend_image(image)
    mask = augmenter.generate_mask_from_bbox(extended_image, SEGMENTATION_MODEL_NAME, DETECTION_MODEL_NAME)
    inverted_mask_image = augmenter.invert_mask(mask)
    mask.save("mask.jpg")
    inverted_mask_image.save("inverted_mask.jpg")
