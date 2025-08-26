from flask import Flask, request, render_template, redirect, url_for
import pytesseract
from PIL import Image, ImageOps, ImageFilter
import cv2
import numpy as np
import re
import csv
import os
from datetime import datetime

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- Configuration ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
RESULTS_FILE = 'expenses.csv'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configure Tesseract path (if not in PATH, adjust for your system)
# Example for Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Example for Linux/macOS (usually in PATH, so often not needed):
# pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract' # Or wherever tesseract is installed

# Initialize CSV file with headers if it doesn't exist
if not os.path.exists(RESULTS_FILE):
    with open(RESULTS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Filename', 'Amount', 'Date', 'Extracted_Text'])

# --- Image Preprocessing Functions ---
def preprocess_image(image_path):
    """
    Applies various preprocessing steps to an image to improve OCR accuracy.
    Uses PIL for basic operations and OpenCV for more advanced ones.
    """
    # Load image with PIL
    img = Image.open(image_path)

    # Convert to grayscale
    img = ImageOps.grayscale(img)

    # Convert PIL Image to OpenCV format (numpy array)
    cv_img = np.array(img)

    # Apply adaptive thresholding (better for uneven lighting)
    # This creates a binary image (black and white)
    _, thresholded_img = cv2.threshold(cv_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Optional: Noise removal (median blur) - can help with small speckles
    denoised_img = cv2.medianBlur(thresholded_img, 3)

    # Optional: Deskewing (correcting image tilt) - more complex to implement fully for demo
    # For a demo, you might skip this or use a simpler rotation if needed.

    # Convert back to PIL Image for Tesseract
    processed_pil_img = Image.fromarray(denoised_img)

    return processed_pil_img

# --- Data Extraction Functions ---
def extract_amount_and_date(text):
    """
    Extracts transfer amount and date from the OCR-ed text using regex.
    This will need to be refined based on actual Thai slip formats.
    """
    amount = None
    date = None

    # Regex for typical Thai Baht amounts:
    # Looks for numbers, potentially with commas, followed by a decimal point and two digits,
    # often preceded by currency symbols or keywords like "บาท" (baht)
    # This is a simplified example, real-world might need more robust patterns.
    # Example: "1,234.50", "500.00", "ยอดเงิน 123.45"
    amount_patterns = r"\d{3}[.]{1}\d{2}"
        # r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*(?:THB|บาท)?', # e.g., 1,234.50 บาท
        # r'(?:THB|บาท)\s*(\d{1,3}(?:,\d{3})*\.\d{2})', # e.g., บาท 1,234.50
        # r'(\d+\.\d{2})', # Simpler match for any X.YY number
        
    for pattern in amount_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Clean up the amount (remove commas) and convert to float
            amount = float(match.group(1).replace(',', ''))
            break

    # Regex for common date formats (DD/MM/YYYY, DD-MM-YYYY, DD MMM YYYY)
    # Thai dates might use Buddhist calendar (BE), which is Gregorian + 543 years.
    # For simplicity, we'll assume Gregorian for parsing, and note the BE conversion.
    date_patterns = r"\d{1,2}[\s\u0E00-\u0E7F\]+.{1}+[\u0E00-\u0E7F]+\.?\s+\d{4}"
        # r'(\d{1,2}/\d{1,2}/\d{2,4})',  # DD/MM/YY or DD/MM/YYYY
        # r'(\d{1,2}-\d{1,2}-\d{2,4})',  # DD-MM-YY or DD-MM-YYYY
        # r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4})', # DD Mon YYYY
        # r'(\d{1,2}\s+(?:ม.ค.|ก.พ.|มี.ค.|เม.ย.|พ.ค.|มิ.ย.|ก.ค.|ส.ค.|ก.ย.|ต.ค.|พ.ย.|ธ.ค.)\s+\d{2,4})', # DD Thai_Mon YYYY (Buddhist year)
        
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
        if match:
            date_str = match.group(1)
            try:
                # Attempt to parse as Gregorian first
                date = datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
            except ValueError:
                try:
                    date = datetime.strptime(date_str, '%d-%m-%Y').strftime('%Y-%m-%d')
                except ValueError:
                    # Handle Thai month abbreviations and potential Buddhist year (BE)
                    # This is a simplification; a full solution would map Thai month names.
                    # For demo, we might just keep the string or try a common Thai format.
                    # For example, if year is > 2500, assume BE and convert to CE.
                    # This requires more complex parsing. For now, let's keep it simple.
                    date = date_str # Keep as string if parsing fails
            break

    return amount, date

# --- Flask Routes ---
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file:
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Preprocess image
            processed_img = preprocess_image(filepath)
            
            # Perform OCR
            # Specify language if needed, e.g., lang='eng+tha' for English and Thai
            extracted_text = pytesseract.image_to_string(processed_img, lang='eng+tha')

            # Extract amount and date
            amount, date = extract_amount_and_date(extracted_text)

            # Record in CSV
            with open(RESULTS_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([filename, amount, date, extracted_text.strip()])

            return render_template('result.html', 
                                   filename=filename,
                                   amount=amount, 
                                   date=date, 
                                   extracted_text=extracted_text.strip())
    return render_template('upload.html')

@app.route('/expenses')
def view_expenses():
    expenses = []
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader) # Skip header
            for row in reader:
                expenses.append(row)
    return render_template('expenses.html', expenses=expenses)

if __name__ == '__main__':
    app.run(debug=True)
