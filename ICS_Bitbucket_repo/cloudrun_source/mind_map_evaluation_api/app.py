from flask import Flask, request, jsonify
from flask_utils import apply_security_headers
from google.cloud import tasks_v2
from gcp import *
from std_response import *
from low_quality_checker import MindMapQualityChecker
import os
import uuid
import json
from typing import Optional
from google.cloud import storage
import logging
app = Flask(__name__)
app.after_request(apply_security_headers)
logger = logging.getLogger()

@app.route('/', methods = ['POST'])
def main():
    

    func_conf = gcp_get_config()
    request_json = request.get_json(silent=True)
    logger.info(f"checking the request_json: {request_json}")
    required_fields = [
        "mainjob-ID",
        "user_id",
        "patterns",
        "mind-map-image-file",
        "component_list",
    ]
    for field in required_fields:
        if field not in request_json or request_json[field] == "":
            return create_response(f"Request must contain {field} and it must not be empty", 400, request.method)
    
    # Extract bucket name and file path from the 'mind-map-image-file' URL
    file_path = request_json['mind-map-image-file']
    bucket_name, file_name = file_path.replace('gs://', '').split('/', 1)
    print(bucket_name,file_name)
    # Check if the file exists in the bucket
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    if not blob.exists():
        logger.error(f"File {file_path} does not exist in bucket {bucket_name}")
        return create_response("This uploaded mind map does not exist in the bucket, please try again.", 404, request.method)
    
    
    logging.info("Start to precheck mind map quality.")
    
    mmp_quality_checker = MindMapQualityChecker(file_name,bucket_name)
    checker_response = mmp_quality_checker.check_mind_map_quality()
    logging.info(f"checking the checker response: {checker_response}")

    
    if checker_response is not True:
        return checker_response
    # mm_url = os.getenv("MM_URL").replace('"', "").strip()
    mindmap_queue = func_conf.get("task_queue_mindmap", "MindMapQueue")
    mindmap_job_id = str(uuid.uuid4())

    payload = {
            "mainjob-ID": request_json["mainjob-ID"],
            "maineval-StartTime": request_json["maineval-StartTime"],
            "user_id": request_json["user_id"],
            "patterns": request_json["patterns"],
            "mind-map-image-file": request_json["mind-map-image-file"],
            "component_list": request_json["component_list"],
            "mindmap_job_id": mindmap_job_id
        }

    if "request_type" in request_json and "user_stage" in request_json:
        payload = {
            "request_type": request_json["request_type"],
            "user_stage": request_json["user_stage"],
            "mainjob-ID": request_json["mainjob-ID"],
            "maineval-StartTime": request_json["maineval-StartTime"],
            "user_id": request_json["user_id"],
            "patterns": request_json["patterns"],
            "mind-map-image-file": request_json["mind-map-image-file"],
            "component_list": request_json["component_list"],
            "mindmap_job_id": mindmap_job_id
        }
    project_id = gcp_project_id()
    region = func_conf.get("region", "")
    project_number = gcp_project_number(project_id)
    mm_url = os.getenv("ICS_MIND_MAP_EVALUATION_CLOUD_RUN_URL").replace('"', "").strip()
    logger.info(f"Checking the mmp pipeline url {mm_url}")
    create_http_task_with_token(
            project_id,
            region,
            mindmap_queue,
            mm_url,
            json.dumps(payload).encode("utf-8"),
            f"{project_number}-compute@developer.gserviceaccount.com",
            mm_url,
        )
    return create_response("Mindmap pipeline started", 200, request.method, subjob_id = mindmap_job_id, user_id = request_json["user_id"])
    

def create_http_task_with_token(
    project: str,
    location: str,
    queue: str,
    url: str,
    payload: bytes,
    service_account_email: str,
    audience: Optional[str] = None,
) -> tasks_v2.Task:
    """Create an HTTP POST task with an OIDC token and an arbitrary payload.
    Args:
        project: The project ID where the queue is located.
        location: The location where the queue is located.
        queue: The ID of the queue to add the task to.
        url: The target URL of the task.
        payload: The payload to send.
        service_account_email: The service account to use for generating the OIDC token.
        audience: Audience to use when generating the OIDC token.
    Returns:
        The newly created task.
    """

    # Create a client.
    client = tasks_v2.CloudTasksClient()

    # Construct the request body.
    task = tasks_v2.Task(
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=url,
            oidc_token=tasks_v2.OidcToken(
                service_account_email=service_account_email,
                audience=audience,
            ),
            body=payload,
            headers={"Content-type": "application/json"},
        ),
    )

    # Use the client to build and send the task.
    return client.create_task(
        tasks_v2.CreateTaskRequest(
            parent=client.queue_path(project, location, queue),
            task=task,
        )
    )