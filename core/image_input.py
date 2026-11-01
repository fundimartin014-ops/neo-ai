import pytesseract
from PIL import Image

def extract_text_from_image(image_path):
    """Read image or diagram and return extracted text."""
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    return text
