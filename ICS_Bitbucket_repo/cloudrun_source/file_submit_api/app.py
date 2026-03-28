from flask import Flask, request, jsonify
from flask_utils import apply_security_headers
from werkzeug.utils import secure_filename
from google.cloud import storage
from std_response import *

app=Flask(__name__)
app.after_request(apply_security_headers)
ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg']
MAX_FILE_SIZE = 1 * 1024 * 1024
PROJECT_ID = gcp_project_id()
BUCKET_NAME = f"unscanned-{PROJECT_ID}"


@app.route('/', methods=['POST'])
def main():
    if request.method != 'POST':
        create_response("Please use POST to request the API", 405, request.method)

    if 'file' not in request.files:
        return create_response("No file part", 400, request.method)
    
    file = request.files['file']
    if file.filename == '':
        return create_response("No selected file", 400, request.method)
    
    if file and allowed_file(file.filename):
        if len(file.read()) > MAX_FILE_SIZE:
            return create_response("The file is too large", 400, request.method)
        file.seek(0)  # Seek to the start of the file after reading it for size check
        filename = secure_filename(file.filename)
        # Make sure to set up Google Cloud Storage credentials
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(
            file.read(),
            content_type=file.content_type
        )
        return create_response("File uploaded successfully", 200, request.method)
    else:
        return create_response("File type not allowed", 200, request.method)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
