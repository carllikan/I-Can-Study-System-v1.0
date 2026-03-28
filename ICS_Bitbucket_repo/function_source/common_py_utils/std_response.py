# standardised API call JSON response creation function
from flask import jsonify, make_response

def create_response(message, code, method, mainjob_id=None, subjob_id=None, request_id=None, user_id=None, summary = None):
    """
    Creates a JSON response with given message and code, and adds CORS headers.
    
    :param message: str, the response message.
    :param code: int, the HTTP status code.
    :return: Response object with the given message, code, and headers.
    """
    response_data = {
        "code": code, 
        "response": message
    }
    # Add additional data if provided
    additional_data = {
        "main_job_id": mainjob_id,
        "sub_job_id": subjob_id,
        "request_id": request_id,
        "user_id": user_id,
        "summary": summary
    }

    for key, value in additional_data.items():
        if value is not None:
            response_data[key] = value

    if any(value is not None for value in additional_data.values()):
        response_data["job_status"] = "finished"
    
    response = make_response(jsonify(response_data), code)
    # Add headers
    # response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", method)
    
    return response